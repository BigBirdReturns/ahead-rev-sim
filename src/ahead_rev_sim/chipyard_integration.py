"""Compatibility surface for the pinned Chipyard subsystem integration."""

from __future__ import annotations

from .chipyard_io import write_chipyard_bundle
from .chipyard_subsystem import (
    CHIPYARD_COMMIT,
    CHIPYARD_CONFIG_CLASS,
    CHIPYARD_CONFIG_PACKAGE,
    CHIPYARD_INTEGRATION_SCHEMA_VERSION,
    CHIPYARD_REFERENCE_BLOB_SHA,
    CHIPYARD_REFERENCE_PATH,
    CHIPYARD_REFERENCE_REF,
    CHIPYARD_REFERENCE_URL,
    CHIPYARD_REPOSITORY,
    CHIPYARD_SCALA_INSTALL_PATH,
    CHIPYARD_SOURCE_WITNESSES,
    CHIPYARD_SUBMODULE_WITNESSES,
    DEFAULT_BASE_ADDRESS,
    ELABORATION_WITNESS_NAME,
    ELABORATION_WITNESS_VALUE,
    build_chipyard_manifest,
    render_baremetal_smoke,
    render_chipyard_scala,
)

__all__ = [
    "CHIPYARD_INTEGRATION_SCHEMA_VERSION",
    "CHIPYARD_REPOSITORY",
    "CHIPYARD_COMMIT",
    "CHIPYARD_CONFIG_PACKAGE",
    "CHIPYARD_CONFIG_CLASS",
    "CHIPYARD_SCALA_INSTALL_PATH",
    "CHIPYARD_SOURCE_WITNESSES",
    "CHIPYARD_SUBMODULE_WITNESSES",
    "CHIPYARD_REFERENCE_REF",
    "CHIPYARD_REFERENCE_PATH",
    "CHIPYARD_REFERENCE_BLOB_SHA",
    "CHIPYARD_REFERENCE_URL",
    "DEFAULT_BASE_ADDRESS",
    "ELABORATION_WITNESS_NAME",
    "ELABORATION_WITNESS_VALUE",
    "render_chipyard_scala",
    "render_baremetal_smoke",
    "build_chipyard_manifest",
    "write_chipyard_bundle",
]
