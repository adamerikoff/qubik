import typing 
import logging

import docker
import docker.errors
import docker.models
import docker.models.containers
import docker.types

from .config import Config

logger = logging.getLogger(__name__)

class DockerResult:
    def __init__(self,
                 action: str,
                 container_id: str,
                 error: typing.Optional[Exception] = None,
                 result: typing.Optional[str] = None): 
        
        self.action: str = action
        self.container_id: str = container_id
        self.error: typing.Optional[Exception] = error
        self.result: typing.Optional[str] = result

        if self.error:
            logger.error(
                "DockerResult created for action '%s' (container_id: %s) with error: %s - Result: %s",
                self.action, self.container_id, self.error, self.result
            )
        else:
            logger.info(
                "DockerResult created for action '%s' (container_id: %s) - Result: %s",
                self.action, self.container_id, self.result
            )

    def __repr__(self) -> str:
        status = "Success" if self.error is None else f"Error: {self.error}"
        return (f"DockerResult(action='{self.action}', container_id='{self.container_id}', "
                f"status='{status}', result='{self.result}')")
    

class Docker:
    def __init__(self,
                 config: Config,
                 client: typing.Optional[docker.DockerClient] = None):

        self.client: docker.DockerClient = client if client else docker.from_env()
        self.config: Config = config
        self.container_id: typing.Optional[str] = None
        self._container: typing.Optional[docker.models.containers.Container] = None

        logger.info("Docker client initialized for image: '%s'", self.config.image)

        if client:
            logger.debug("Using provided Docker client instance.")
        else:
            logger.debug("Initialized Docker client from environment variables.")

    def run(self) -> DockerResult:
        logger.info(f"Attempting to run task '{self.config.name}' with image '{self.config.image}'")

        # 1. Pull the Docker image
        try:
            logger.info(f"Pulling image: '{self.config.image}'...")
            self.client.images.pull(self.config.image)
            logger.info(f"Image '{self.config.image}' pulled successfully.")
        except docker.errors.ImageNotFound:
            err_msg = f"Image '{self.config.image}' not found."
            logger.error(err_msg)
            return DockerResult(action="start", container_id=None, error=docker.errors.ImageNotFound(err_msg), result="image_not_found")
        except docker.errors.APIError as e:
            logger.error(f"Error pulling image '{self.config.image}': {e}")
            return DockerResult(action="start", container_id=None, error=e, result="image_pull_failed")
        except Exception as e:
            logger.error(f"An unexpected error occurred during image pull for '{self.config.image}': {e}")
            return DockerResult(action="start", container_id=None, error=e, result="unexpected_error")


        # 2. Prepare container configuration
        restart_policy_dict = {"Name": self.config.restart_policy} if self.config.restart_policy else {}

        # Convert CPU to nanoCPUs
        nano_cpus = int(self.config.cpu * (10**9)) if self.config.cpu > 0 else None
        
        container_kwargs = {
            "image": self.config.image,
            "command": self.config.cmd if self.config.cmd else None, # Pass the command list
            "environment": self.config.env,
            "name": self.config.name,
            "restart_policy": restart_policy_dict,
            "publish_all_ports": True, # As per the Go example
            "mem_limit": self.config.memory if self.config.memory > 0 else None,
            "nano_cpus": nano_cpus,
            "tty": False,
        }
        
        container_kwargs = {k: v for k, v in container_kwargs.items() if v is not None}
        try:
            logger.info(f"Creating container '{self.config.name}' with config: {container_kwargs}")
            self._container = self.client.containers.create(**container_kwargs)
            self.container_id = self._container.id
            logger.info(f"Container '{self.config.name}' created with ID: {self.container_id}")
        except docker.errors.APIError as e:
            logger.error(f"Error creating container '{self.config.name}': {e}")
            return DockerResult(action="start", container_id=None, error=e, result="container_creation_failed")
        except Exception as e:
            logger.error(f"An unexpected error occurred during container creation for '{self.config.name}': {e}")
            return DockerResult(action="start", container_id=None, error=e, result="unexpected_error")

        try:
            logger.info(f"Starting container '{self.container_id}'...")
            if self._container:
                self._container.start()
                logger.info(f"Container '{self.container_id}' started successfully.")
            else:
                raise RuntimeError("Container object not found after creation.")
        except docker.errors.APIError as e:
            logger.error(f"Error starting container '{self.container_id}': {e}")
            return DockerResult(action="start", container_id=self.container_id, error=e, result="container_start_failed")
        except Exception as e:
            logger.error(f"An unexpected error occurred during container start for '{self.container_id}': {e}")
            return DockerResult(action="start", container_id=self.container_id, error=e, result="unexpected_error")

        try:
            if self._container:
                logs = self._container.logs(stdout=True, stderr=True, stream=False).decode('utf-8')
                logger.info(f"Logs for container '{self.container_id}':\n{logs}")
            else:
                logger.warning("No container object to get logs from after start.")
        except docker.errors.APIError as e:
            logger.warning(f"Error getting logs for container '{self.container_id}': {e}")
        except Exception as e:
            logger.warning(f"An unexpected error occurred while getting logs for '{self.container_id}': {e}")

        return DockerResult(action="start", container_id=self.container_id, result="success")


    def stop(self) -> DockerResult:
        if not self.container_id:
            logger.warning("No container ID set for Docker object. Cannot stop an unmanaged container.")
            return DockerResult(action="stop", container_id=None, error=ValueError("No container ID to stop"), result="no_container_id")

        logger.info(f"Attempting to stop and remove container: '{self.container_id}'")

        try:
            if not self._container or self._container.id != self.container_id:
                self._container = self.client.containers.get(self.container_id)

            logger.info(f"Stopping container '{self.container_id}'...")
            self._container.stop(timeout=10)
            logger.info(f"Container '{self.container_id}' stopped successfully.")

            logger.info(f"Removing container '{self.container_id}'...")
            self._container.remove(v=True, link=False, force=False)
            logger.info(f"Container '{self.container_id}' removed successfully.")

            self.container_id = None
            self._container = None

            return DockerResult(action="stop", container_id=self.container_id, result="success")

        except docker.errors.NotFound:
            err_msg = f"Container '{self.container_id}' not found. It might already be stopped/removed."
            logger.warning(err_msg)
            return DockerResult(action="stop", container_id=self.container_id,
                                error=docker.errors.NotFound(err_msg), result="container_not_found")
        except docker.errors.APIError as e:
            logger.error(f"Error stopping or removing container '{self.container_id}': {e}")
            return DockerResult(action="stop", container_id=self.container_id, error=e, result="api_error")
        except Exception as e:
            logger.error(f"An unexpected error occurred during stop/remove for container '{self.container_id}': {e}")
            return DockerResult(action="stop", container_id=self.container_id, error=e, result="unexpected_error")
