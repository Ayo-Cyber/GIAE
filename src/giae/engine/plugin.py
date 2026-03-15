"""
Plugin architecture for GIAE.

Defines the interface for extension plugins (HMMER, ESM-2, BLAST).
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional
import importlib
import logging

from giae.models.evidence import Evidence
from giae.models.gene import Gene

logger = logging.getLogger(__name__)


class AnalysisPlugin(ABC):
    """Base class for all analysis plugins."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the plugin."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Version of the plugin."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if plugin dependencies are installed and available."""
        pass

    @abstractmethod
    def scan(self, gene: Gene) -> List[Evidence]:
        """
        Scan a gene and return evidence.

        Args:
            gene: The gene to analyze.

        Returns:
            List of Evidence objects.
        """
        pass


class PluginManager:
    """Manages discovery and execution of analysis plugins."""

    def __init__(self):
        self._plugins: List[AnalysisPlugin] = []
        self._discover_plugins()

    def _discover_plugins(self):
        """Discover and load available plugins."""
        # Built-in plugins could be registered here
        # For this refactor, we will manually register the new HMMER plugin
        # later when it is implemented.
        pass

    def register(self, plugin: AnalysisPlugin):
        """Register a plugin instance."""
        if plugin.is_available():
            self._plugins.append(plugin)
            logger.info(f"Registered plugin: {plugin.name} v{plugin.version}")
        else:
            logger.debug(f"Plugin {plugin.name} unavailable (dependencies missing)")

    def scan_gene(self, gene: Gene) -> List[Evidence]:
        """Run all registered plugins on a gene."""
        results = []
        for plugin in self._plugins:
            try:
                evidence = plugin.scan(gene)
                results.extend(evidence)
            except Exception as e:
                logger.error(f"Plugin {plugin.name} failed on gene {gene.id}: {e}")
        return results

    @property
    def active_plugins(self) -> List[str]:
        """List names of active plugins."""
        return [p.name for p in self._plugins]
