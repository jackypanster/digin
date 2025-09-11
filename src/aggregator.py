"""父級摘要聚合。

核心規則：
- 類型(kind)推斷：按子摘要統計（service/lib/test…）+ 特例（service+lib → infra）。
- 摘要：描述子模塊數量、代表能力與樣例名稱，突出父目錄角色。
- 合併：能力去重限量；公共接口分類合併（每類最多 10 條）；依賴/配置用集合去重；
- 風險：按提及頻次排序選取；證據：子 `digest.json` + 直屬文件列表。
- 置信度：均值 − 方差懲罰 + 子數量加成，最後截斷至 0–100。

目標：讓父目錄像「主頁」一樣快速傳達重點，便於人快速掃描理解。
"""

from pathlib import Path
from typing import Dict, Any, List, Set, Optional
from datetime import datetime
from collections import Counter

from .config import DigginSettings
from .__version__ import __version__


class SummaryAggregator:
    """Aggregates child directory summaries for parent directories."""
    
    def __init__(self, settings: DigginSettings):
        """Initialize aggregator.
        
        Args:
            settings: Configuration settings
        """
        self.settings = settings
    
    def aggregate_summaries(self, directory: Path, 
                          child_digests: List[Dict[str, Any]], 
                          direct_files_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Aggregate child summaries for a parent directory.
        
        Args:
            directory: Parent directory
            child_digests: List of child directory digests
            direct_files_info: Information about direct files in parent directory
            
        Returns:
            Aggregated digest for parent directory
        """
        # Base digest structure
        digest = {
            "name": directory.name,
            "path": str(directory),
            "kind": self._determine_aggregated_kind(child_digests, direct_files_info),
            "summary": self._generate_aggregated_summary(directory, child_digests, direct_files_info),
            "capabilities": self._merge_capabilities(child_digests),
            "public_interfaces": self._merge_public_interfaces(child_digests),
            "dependencies": self._merge_dependencies(child_digests),
            "configuration": self._merge_configuration(child_digests),
            "risks": self._merge_risks(child_digests),
            "evidence": self._create_evidence(child_digests, direct_files_info),
            "confidence": self._calculate_aggregate_confidence(child_digests),
            "analyzed_at": datetime.now().isoformat(),
            "analyzer_version": __version__
        }
        
        # Remove empty sections
        return self._clean_empty_fields(digest)
    
    def _determine_aggregated_kind(self, child_digests: List[Dict[str, Any]], 
                                  direct_files_info: Optional[Dict[str, Any]]) -> str:
        """Determine the kind of aggregated directory.
        
        Args:
            child_digests: Child directory digests
            direct_files_info: Direct files information
            
        Returns:
            Directory kind classification
        """
        if not child_digests:
            return "unknown"
        
        # Count kinds from children
        kind_counts = Counter(digest.get("kind", "unknown") for digest in child_digests)
        
        # If all children are the same kind, inherit it
        if len(kind_counts) == 1:
            return list(kind_counts.keys())[0]
        
        # Special aggregation rules
        most_common_kind = kind_counts.most_common(1)[0][0]
        
        # If majority are services, this is likely a service collection
        if kind_counts.get("service", 0) >= len(child_digests) * 0.6:
            return "service"
        
        # If majority are libs, this is likely a lib collection
        if kind_counts.get("lib", 0) >= len(child_digests) * 0.6:
            return "lib"
        
        # If majority are tests, this is likely a test suite
        if kind_counts.get("test", 0) >= len(child_digests) * 0.6:
            return "test"
        
        # If contains mix of services and libs, likely "infra"
        if "service" in kind_counts and "lib" in kind_counts:
            return "infra"
        
        # Default to most common kind
        return most_common_kind
    
    def _generate_aggregated_summary(self, directory: Path, 
                                   child_digests: List[Dict[str, Any]],
                                   direct_files_info: Optional[Dict[str, Any]]) -> str:
        """Generate summary for aggregated directory."""
        if not child_digests:
            return f"{directory.name} 目录（暂无子模块分析结果）"
        
        child_names = [digest.get("name", "未知模块") for digest in child_digests]
        child_count = len(child_names)
        dominant_kind = self._get_dominant_kind(child_digests)
        
        summary = self._get_kind_summary(dominant_kind, child_count)
        summary += self._add_capabilities_info(child_digests)
        summary += self._add_child_names_info(child_names, child_count)
        
        return summary
    
    def _get_dominant_kind(self, child_digests: List[Dict[str, Any]]) -> str:
        """Get the dominant kind from child digests."""
        kind_counts = Counter(digest.get("kind", "unknown") for digest in child_digests)
        return kind_counts.most_common(1)[0][0]
    
    def _get_kind_summary(self, dominant_kind: str, child_count: int) -> str:
        """Get summary text based on dominant kind."""
        kind_summaries = {
            "service": f"包含 {child_count} 个业务服务模块",
            "lib": f"包含 {child_count} 个工具库和通用组件", 
            "test": f"包含 {child_count} 个测试模块",
            "ui": f"包含 {child_count} 个用户界面组件",
            "config": f"包含 {child_count} 个配置相关模块",
        }
        return kind_summaries.get(dominant_kind, f"包含 {child_count} 个子模块")
    
    def _add_capabilities_info(self, child_digests: List[Dict[str, Any]]) -> str:
        """Add capabilities information to summary."""
        all_capabilities = []
        for digest in child_digests:
            capabilities = digest.get("capabilities", [])
            all_capabilities.extend(capabilities[:2])  # Top 2 from each
        
        if all_capabilities:
            unique_capabilities = list(set(all_capabilities))[:3]  # Top 3 unique
            return f"，主要提供：{' | '.join(unique_capabilities)}"
        return ""
    
    def _add_child_names_info(self, child_names: List[str], child_count: int) -> str:
        """Add child names information to summary."""
        if child_count <= 3:
            return f"（{' | '.join(child_names)}）"
        else:
            return f"（包括 {' | '.join(child_names[:3])} 等）"
    
    def _merge_capabilities(self, child_digests: List[Dict[str, Any]]) -> List[str]:
        """Merge capabilities from child directories.
        
        Args:
            child_digests: Child directory digests
            
        Returns:
            Merged list of capabilities
        """
        all_capabilities = []
        capability_counts = Counter()
        
        for digest in child_digests:
            capabilities = digest.get("capabilities", [])
            all_capabilities.extend(capabilities)
            for cap in capabilities:
                capability_counts[cap] += 1
        
        # Return most common capabilities, avoiding duplicates
        merged_capabilities = []
        seen_keywords = set()
        
        for capability, count in capability_counts.most_common():
            # Simple deduplication by checking key words
            key_words = set(capability.lower().split())
            if not key_words.intersection(seen_keywords):
                merged_capabilities.append(capability)
                seen_keywords.update(key_words)
                
                if len(merged_capabilities) >= 8:  # Limit to 8 capabilities
                    break
        
        return merged_capabilities
    
    def _merge_public_interfaces(self, child_digests: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Merge public interfaces from child directories.
        
        Args:
            child_digests: Child directory digests
            
        Returns:
            Merged public interfaces
        """
        merged_interfaces: Dict[str, List[Dict[str, Any]]] = {
            "http": [],
            "rpc": [],
            "cli": [],
            "api": []
        }
        
        for digest in child_digests:
            interfaces = digest.get("public_interfaces", {})
            
            for interface_type, interface_list in interfaces.items():
                if interface_type in merged_interfaces and interface_list:
                    merged_interfaces[interface_type].extend(interface_list)
        
        # Remove duplicates and limit count
        for interface_type in merged_interfaces:
            # Simple deduplication by converting to string and back
            seen = set()
            unique_interfaces = []
            
            for interface in merged_interfaces[interface_type]:
                interface_key = str(sorted(interface.items()))
                if interface_key not in seen:
                    seen.add(interface_key)
                    unique_interfaces.append(interface)
                    
                if len(unique_interfaces) >= 10:  # Limit per type
                    break
            
            merged_interfaces[interface_type] = unique_interfaces
        
        # Remove empty interface types
        return {k: v for k, v in merged_interfaces.items() if v}
    
    def _merge_dependencies(self, child_digests: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Merge dependencies from child directories.
        
        Args:
            child_digests: Child directory digests
            
        Returns:
            Merged dependencies
        """
        internal_deps: Set[str] = set()
        external_deps: Set[str] = set()
        
        for digest in child_digests:
            dependencies = digest.get("dependencies", {})
            
            internal_deps.update(dependencies.get("internal", []))
            external_deps.update(dependencies.get("external", []))
        
        merged_deps = {}
        if internal_deps:
            merged_deps["internal"] = sorted(list(internal_deps))
        if external_deps:
            merged_deps["external"] = sorted(list(external_deps))
            
        return merged_deps
    
    def _merge_configuration(self, child_digests: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Merge configuration from child directories.
        
        Args:
            child_digests: Child directory digests
            
        Returns:
            Merged configuration
        """
        env_vars: Set[str] = set()
        config_files: Set[str] = set()
        
        for digest in child_digests:
            configuration = digest.get("configuration", {})
            
            env_vars.update(configuration.get("env", []))
            config_files.update(configuration.get("files", []))
        
        merged_config = {}
        if env_vars:
            merged_config["env"] = sorted(list(env_vars))
        if config_files:
            merged_config["files"] = sorted(list(config_files))
            
        return merged_config
    
    def _merge_risks(self, child_digests: List[Dict[str, Any]]) -> List[str]:
        """Merge risks from child directories.
        
        Args:
            child_digests: Child directory digests
            
        Returns:
            Merged list of risks
        """
        risk_counts = Counter()
        
        for digest in child_digests:
            risks = digest.get("risks", [])
            for risk in risks:
                risk_counts[risk] += 1
        
        # Return risks mentioned by multiple children or high-priority ones
        merged_risks = []
        for risk, count in risk_counts.most_common():
            if count > 1 or len(merged_risks) < 3:  # Multi-mention or top 3
                merged_risks.append(risk)
                
            if len(merged_risks) >= 6:  # Limit to 6 risks
                break
        
        return merged_risks
    
    def _create_evidence(self, child_digests: List[Dict[str, Any]], 
                        direct_files_info: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Create evidence for aggregated directory.
        
        Args:
            child_digests: Child directory digests
            direct_files_info: Direct files information
            
        Returns:
            Evidence dictionary
        """
        evidence_files = []
        
        # Add files from children (digest.json files)
        for digest in child_digests:
            child_path = digest.get("path", "")
            if child_path:
                evidence_files.append(f"{child_path}/digest.json")
        
        # Add direct files if any
        if direct_files_info:
            for file_info in direct_files_info.get("files", []):
                file_path = file_info.get("path", "")
                if file_path:
                    evidence_files.append(file_path)
        
        return {"files": evidence_files}
    
    def _calculate_aggregate_confidence(self, child_digests: List[Dict[str, Any]]) -> int:
        """Calculate aggregate confidence score.
        
        Args:
            child_digests: Child directory digests
            
        Returns:
            Aggregate confidence score (0-100)
        """
        if not child_digests:
            return 30  # Low confidence for empty aggregation
        
        confidences = [digest.get("confidence", 50) for digest in child_digests]
        
        # Weighted average with penalty for low confidence children
        avg_confidence = sum(confidences) / len(confidences)
        
        # Penalty for inconsistent confidence (high variance)
        if len(confidences) > 1:
            variance = sum((c - avg_confidence) ** 2 for c in confidences) / len(confidences)
            variance_penalty = min(variance / 100, 20)  # Max 20 point penalty
            avg_confidence -= variance_penalty
        
        # Bonus for having more children (more evidence)
        child_count_bonus = min(len(child_digests) * 2, 10)  # Max 10 point bonus
        avg_confidence += child_count_bonus
        
        # Ensure within bounds
        return max(0, min(100, int(avg_confidence)))
    
    def _clean_empty_fields(self, digest: Dict[str, Any]) -> Dict[str, Any]:
        """Remove empty fields from digest.
        
        Args:
            digest: Digest dictionary
            
        Returns:
            Cleaned digest dictionary
        """
        cleaned = {}
        
        for key, value in digest.items():
            if isinstance(value, list) and not value:
                continue  # Skip empty lists
            elif isinstance(value, dict) and not value:
                continue  # Skip empty dicts
            elif value is None or value == "":
                continue  # Skip None or empty strings
            else:
                cleaned[key] = value
                
        return cleaned
