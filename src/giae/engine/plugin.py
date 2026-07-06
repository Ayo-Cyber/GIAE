"""
Plugin architecture for GIAE.

Defines the interface for extension plugins (HMMER, ESM-2, BLAST).
"""

import logging
from abc import ABC, abstractmethod

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
    def scan(self, gene: Gene) -> list[Evidence]:
        """
        Scan a gene and return evidence.

        Args:
            gene: The gene to analyze.

        Returns:
            List of Evidence objects.
        """
        pass

    def supports_batch(self) -> bool:
        """Whether this plugin has an efficient scan_batch (one call for many
        genes). Plugins backed by a subprocess that loads a large database per
        invocation (e.g. Diamond) should override scan_batch and return True
        here so the manager pre-scans the whole genome in a single call."""
        return False

    def scan_batch(self, genes: list[Gene]) -> dict[str, list[Evidence]]:
        """Scan many genes at once, keyed by gene id. Default implementation
        just loops scan(); batch-capable plugins override this with a single
        underlying call."""
        return {gene.id: self.scan(gene) for gene in genes}


class PluginManager:
    """Manages discovery and execution of analysis plugins."""

    def __init__(self) -> None:
        self._plugins: list[AnalysisPlugin] = []
        # Pre-computed evidence from batch-capable plugins, keyed by plugin
        # name then gene id. Populated by prescan(); consumed by scan_gene().
        self._batch_cache: dict[str, dict[str, list[Evidence]]] = {}
        self._discover_plugins()

    def _discover_plugins(self) -> None:
        """Discover and load available plugins."""
        # Built-in plugins could be registered here
        # For this refactor, we will manually register the new HMMER plugin
        # later when it is implemented.
        pass

    def register(self, plugin: AnalysisPlugin) -> None:
        """Register a plugin instance."""
        if plugin.is_available():
            self._plugins.append(plugin)
            logger.info(f"Registered plugin: {plugin.name} v{plugin.version}")
        else:
            logger.debug(f"Plugin {plugin.name} unavailable (dependencies missing)")

    def prescan(self, genes: list[Gene]) -> None:
        """Run every batch-capable plugin once over all genes and cache the
        results, so the per-gene scan_gene() loop can read them instead of
        invoking a heavyweight subprocess per gene. Safe to call once before
        a parallel per-gene interpretation pass — the cache is then read-only."""
        self._batch_cache = {}
        for plugin in self._plugins:
            if not plugin.supports_batch():
                continue
            try:
                self._batch_cache[plugin.name] = plugin.scan_batch(genes)
                logger.info("Batch pre-scan: %s over %d genes", plugin.name, len(genes))
            except Exception as e:  # noqa: BLE001
                logger.error("Batch pre-scan failed for %s: %s", plugin.name, e)

    def scan_gene(self, gene: Gene) -> list[Evidence]:
        """Run all registered plugins on a gene. Batch-capable plugins whose
        results were pre-computed by prescan() are read from the cache."""
        results = []
        for plugin in self._plugins:
            try:
                cached = self._batch_cache.get(plugin.name)
                if cached is not None:
                    results.extend(cached.get(gene.id, []))
                else:
                    results.extend(plugin.scan(gene))
            except Exception as e:
                logger.error(f"Plugin {plugin.name} failed on gene {gene.id}: {e}")
        return results

    @property
    def active_plugins(self) -> list[str]:
        """List names of active plugins."""
        return [p.name for p in self._plugins]
