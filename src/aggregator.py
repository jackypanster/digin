"""
Summary aggregation for parent directories
"""

from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
from collections import Counter

from .config import DigginSettings
from .__version__ import __version__


class SummaryAggregator:
    """Aggregates summaries from child directories"""
    
    def __init__(self, settings: DigginSettings):
        self.settings = settings
    
    def aggregate_directory(
        self,
        directory: Path,
        root_path: Path,
        directory_info: Dict[str, Any],
        child_digests: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Aggregate information from child directories
        
        Args:
            directory: Current directory being analyzed
            root_path: Root directory of analysis
            directory_info: Information about current directory
            child_digests: List of child directory digests
            
        Returns:
            Aggregated digest
        """
        
        # Base information
        digest = {
            "name": directory.name,
            "path": str(directory.relative_to(root_path)) if directory != root_path else ".",
            "kind": self._infer_directory_kind(directory, directory_info, child_digests),
            "summary": self._generate_summary(directory, directory_info, child_digests),
            "capabilities": self._aggregate_capabilities(child_digests),
            "dependencies": self._aggregate_dependencies(child_digests),
            "evidence": self._collect_evidence(directory_info, child_digests),
            "confidence": self._calculate_confidence(directory_info, child_digests),
            "analyzed_at": datetime.utcnow().isoformat() + "Z",
            "analyzer_version": f"digin-{__version__}",
        }
        
        # Add optional fields if they have content
        public_interfaces = self._aggregate_public_interfaces(child_digests)
        if public_interfaces:
            digest["public_interfaces"] = public_interfaces
        
        configuration = self._aggregate_configuration(child_digests)
        if configuration:
            digest["configuration"] = configuration
        
        risks = self._aggregate_risks(child_digests)
        if risks:
            digest["risks"] = risks
        
        return digest
    
    def _infer_directory_kind(
        self,
        directory: Path,
        directory_info: Dict[str, Any],
        child_digests: List[Dict[str, Any]]
    ) -> str:
        """Infer the kind of directory based on name and contents"""
        
        dir_name = directory.name.lower()
        
        # Check common directory name patterns
        if dir_name in {"test", "tests", "__tests__", "spec", "specs"}:
            return "test"
        
        if dir_name in {"doc", "docs", "documentation", "readme"}:
            return "docs"
        
        if dir_name in {"config", "configuration", "settings", "conf"}:
            return "config"
        
        if dir_name in {"lib", "libs", "library", "libraries", "utils", "utilities", "common", "shared"}:
            return "lib"
        
        if dir_name in {"ui", "frontend", "web", "client", "views", "components"}:
            return "ui"
        
        if dir_name in {"service", "services", "api", "server", "backend"}:
            return "service"
        
        if dir_name in {"infra", "infrastructure", "deployment", "deploy", "ops", "devops"}:
            return "infra"
        
        # Infer from child kinds
        if child_digests:
            child_kinds = [child.get("kind", "unknown") for child in child_digests]
            kind_counts = Counter(child_kinds)
            
            # If majority of children are of the same kind, use that
            most_common = kind_counts.most_common(1)
            if most_common and most_common[0][1] > len(child_kinds) / 2:
                return most_common[0][0]
        
        # Check file types for clues
        files = directory_info.get("files", [])
        if files:
            extensions = [f.get("extension", "").lower() for f in files]
            
            if any(ext in {".html", ".css", ".js", ".jsx", ".tsx", ".vue"} for ext in extensions):
                return "ui"
            
            if any(ext in {".py", ".java", ".go", ".rs", ".cpp"} for ext in extensions):
                # Check for main/server patterns
                filenames = [f.get("name", "").lower() for f in files]
                if any("main" in name or "server" in name or "app" in name for name in filenames):
                    return "service"
                return "lib"
        
        return "unknown"
    
    def _generate_summary(
        self,
        directory: Path,
        directory_info: Dict[str, Any],
        child_digests: List[Dict[str, Any]]
    ) -> str:
        """Generate summary for directory"""
        
        dir_name = directory.name
        child_count = len(child_digests)
        file_count = len(directory_info.get("files", []))
        
        if child_count == 0:
            return f"+ {file_count} *‡ö„îU"
        
        # Aggregate child summaries
        child_summaries = []
        for child in child_digests:
            summary = child.get("summary", "")
            if summary and len(summary) < 100:  # Keep only short summaries
                child_summaries.append(summary)
        
        if child_summaries:
            # Use the first few child summaries
            combined = "".join(child_summaries[:3])
            if child_count > 3:
                return f"+ {child_count} *P!W{combined}I"
            else:
                return f"+{combined}"
        else:
            return f"+ {child_count} *PîUŒ {file_count} *‡ö„ÄÇîU"
    
    def _aggregate_capabilities(self, child_digests: List[Dict[str, Any]]) -> List[str]:
        """Aggregate capabilities from children"""
        all_capabilities = []
        
        for child in child_digests:
            capabilities = child.get("capabilities", [])
            all_capabilities.extend(capabilities)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_capabilities = []
        for cap in all_capabilities:
            if cap not in seen:
                seen.add(cap)
                unique_capabilities.append(cap)
        
        # Return top 10 most relevant capabilities
        return unique_capabilities[:10]
    
    def _aggregate_dependencies(self, child_digests: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Aggregate dependencies from children"""
        internal_deps = set()
        external_deps = set()
        
        for child in child_digests:
            deps = child.get("dependencies", {})
            
            internal_deps.update(deps.get("internal", []))
            external_deps.update(deps.get("external", []))
        
        result = {}
        if internal_deps:
            result["internal"] = sorted(list(internal_deps))
        if external_deps:
            result["external"] = sorted(list(external_deps))
        
        return result
    
    def _aggregate_public_interfaces(self, child_digests: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """Aggregate public interfaces from children"""
        interfaces = {}
        
        for child in child_digests:
            child_interfaces = child.get("public_interfaces", {})
            
            for interface_type, interface_list in child_interfaces.items():
                if interface_type not in interfaces:
                    interfaces[interface_type] = []
                interfaces[interface_type].extend(interface_list)
        
        return interfaces
    
    def _aggregate_configuration(self, child_digests: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Aggregate configuration from children"""
        env_vars = set()
        config_files = set()
        
        for child in child_digests:
            config = child.get("configuration", {})
            
            env_vars.update(config.get("env", []))
            config_files.update(config.get("files", []))
        
        result = {}
        if env_vars:
            result["env"] = sorted(list(env_vars))
        if config_files:
            result["files"] = sorted(list(config_files))
        
        return result
    
    def _aggregate_risks(self, child_digests: List[Dict[str, Any]]) -> List[str]:
        """Aggregate risks from children"""
        all_risks = set()
        
        for child in child_digests:
            risks = child.get("risks", [])
            all_risks.update(risks)
        
        return sorted(list(all_risks))
    
    def _collect_evidence(
        self,
        directory_info: Dict[str, Any],
        child_digests: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """Collect evidence files"""
        files = []
        
        # Add direct files
        for file_info in directory_info.get("files", []):
            files.append(file_info["name"])
        
        # Add child evidence
        for child in child_digests:
            child_evidence = child.get("evidence", {}).get("files", [])
            files.extend(child_evidence)
        
        return {"files": files[:20]}  # Limit to 20 files
    
    def _calculate_confidence(
        self,
        directory_info: Dict[str, Any],
        child_digests: List[Dict[str, Any]]
    ) -> int:
        """Calculate confidence level"""
        
        # Base confidence
        confidence = 50
        
        # Increase if we have child digests
        if child_digests:
            child_confidences = [child.get("confidence", 50) for child in child_digests]
            avg_child_confidence = sum(child_confidences) / len(child_confidences)
            confidence = int(avg_child_confidence * 0.8)  # Slight reduction for aggregation
        
        # Increase if we have files
        file_count = len(directory_info.get("files", []))
        if file_count > 0:
            confidence += min(file_count * 2, 20)  # Up to 20 points for files
        
        # Ensure within bounds
        return max(10, min(confidence, 95))  # Keep between 10-95