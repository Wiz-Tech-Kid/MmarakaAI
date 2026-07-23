"""Central project configuration for VenturePulse.

This module keeps filesystem paths and small configuration helpers in one
place. The rest of the codebase should import paths from here instead of
hard-coding directory names, which makes the project easier to move, test, and
deploy later.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

RAW_DATA_DIR = DATA_DIR / "raw"
EXTERNAL_DATA_DIR = DATA_DIR / "external"
MODEL_DIR = PROJECT_ROOT / "models"
OUTPUT_ROOT = Path(os.getenv("MMARAKA_OUTPUT_ROOT", str(PROJECT_ROOT / "output")))
OUTPUT_DIR = OUTPUT_ROOT
PROCESSED_DATA_DIR = OUTPUT_DIR / "processed"
NOTEBOOK_DIR = PROJECT_ROOT / "notebooks"


@dataclass(frozen=True, slots=True)
class ProjectPaths:
    """Container for all important VenturePulse directories.

    Attributes:
        project_root: Root directory for the repository.
        raw_data_dir: Location for original source data files.
        processed_data_dir: Location for cleaned and transformed datasets.
        external_data_dir: Location for external reference datasets.
        model_dir: Location for serialized model artifacts.
        output_dir: Location for reports, predictions, and other outputs.
        notebook_dir: Location for exploratory notebooks.

    The dataclass gives future contributors a single typed object to pass into
    pipelines, CLIs, or tests when they need path configuration.
    """

    project_root: Path = PROJECT_ROOT
    raw_data_dir: Path = RAW_DATA_DIR
    processed_data_dir: Path = PROCESSED_DATA_DIR
    external_data_dir: Path = EXTERNAL_DATA_DIR
    model_dir: Path = MODEL_DIR
    output_dir: Path = OUTPUT_DIR
    notebook_dir: Path = NOTEBOOK_DIR

    def all_directories(self) -> tuple[Path, ...]:
        """Return every directory that should exist for the project.

        Returns:
            A tuple of configured directories. This is used by
            ``ensure_directories`` and can also be useful in tests.

        TODO:
            Add environment-specific paths if the project later supports
            development, staging, and production deployments.
        """

        return (
            self.raw_data_dir,
            self.processed_data_dir,
            self.external_data_dir,
            self.model_dir,
            self.output_dir,
            self.notebook_dir,
        )

    def as_dict(self) -> dict[str, str]:
        """Represent configured paths as plain strings.

        Returns:
            A dictionary mapping friendly path names to absolute path strings.
            This format is convenient for logging, JSON reports, and debug
            output.

        TODO:
            Include additional runtime settings once model training and
            deployment configuration are added.
        """

        return {
            "project_root": str(self.project_root),
            "raw_data_dir": str(self.raw_data_dir),
            "processed_data_dir": str(self.processed_data_dir),
            "external_data_dir": str(self.external_data_dir),
            "model_dir": str(self.model_dir),
            "output_dir": str(self.output_dir),
            "notebook_dir": str(self.notebook_dir),
        }


DEFAULT_PATHS = ProjectPaths()


def ensure_directories(paths: ProjectPaths = DEFAULT_PATHS) -> None:
    """Create configured project directories if they are missing.

    Args:
        paths: A ``ProjectPaths`` instance describing the folders VenturePulse
            expects to use.

    Returns:
        None. The function creates directories as a side effect.

    Raises:
        OSError: If a directory cannot be created because of permissions,
            invalid paths, or filesystem errors.

    TODO:
        Add stricter checks for writable directories before production runs.
    """

    try:
        for directory in paths.all_directories():
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug("Verified project directory: %s", directory)
    except OSError:
        logger.exception("Unable to create one or more project directories.")
        raise


def describe_paths(paths: ProjectPaths = DEFAULT_PATHS) -> dict[str, str]:
    """Return a log-friendly summary of important project paths.

    Args:
        paths: Path configuration to describe.

    Returns:
        A dictionary containing absolute paths as strings.

    TODO:
        Surface this information in a future CLI command or dashboard debug
        page so new contributors can quickly verify their setup.
    """

    try:
        path_summary = paths.as_dict()
        logger.info("Loaded VenturePulse path configuration.")
        return path_summary
    except Exception:
        logger.exception("Failed to describe project paths.")
        raise


if __name__ == "__main__":
    ensure_directories()
    for name, path in describe_paths().items():
        logger.info("%s: %s", name, path)
