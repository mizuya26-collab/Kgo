"""
Kgo Autonomous Engine
Central safety and evolution configuration.
"""

from dataclasses import dataclass, field


@dataclass
class MutationBudget:
    """自己改造の上限"""

    max_changed_files: int = 5
    max_changed_lines: int = 300
    max_dependency_changes: int = 2
    max_repair_attempts: int = 3
    max_evolution_cycles: int = 8
    max_tool_install_attempts: int = 2


@dataclass
class SafetyPolicy:
    """自己修復・自己進化の安全ポリシー"""

    dry_run: bool = True

    # 自動実行可能な最大信頼度
    auto_repair_confidence: float = 0.90

    # 安全な操作のみ許可する信頼度
    safe_repair_confidence: float = 0.70

    # これ未満なら人間へエスカレーション
    escalation_confidence: float = 0.50

    # 重大操作は自動実行しない
    require_approval_for_system_changes: bool = True
    require_approval_for_dependency_changes: bool = True
    require_approval_for_large_mutations: bool = True

    # 同じ修復を無限に繰り返さない
    prevent_duplicate_repairs: bool = True


@dataclass
class EvolutionConfig:
    """自己進化設定"""

    enabled: bool = True

    # 改善しなかった変更を採用しない
    require_score_improvement: bool = True

    # 回帰テスト必須
    require_regression_tests: bool = True

    # 失敗した変更を永続化しない
    rollback_on_verification_failure: bool = True

    # GitHubへ保存する世代間隔
    github_commit_every_generation: int = 1


@dataclass
class EngineConfig:
    """Autonomous Engine 全体設定"""

    project_name: str = "Kgo"

    mutation: MutationBudget = field(
        default_factory=MutationBudget
    )

    safety: SafetyPolicy = field(
        default_factory=SafetyPolicy
    )

    evolution: EvolutionConfig = field(
        default_factory=EvolutionConfig
    )


CONFIG = EngineConfig()
