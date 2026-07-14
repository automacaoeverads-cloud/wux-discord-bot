from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class RollResult:
    die: int
    modifier: int
    total: int
    dc: int
    success: bool
    critical: bool  # 20 natural
    fumble: bool    # 1 natural

    def describe(self, attr_label: str) -> str:
        flag = ""
        if self.critical:
            flag = " — **CRÍTICO!**"
        elif self.fumble:
            flag = " — **DESASTRE!**"
        outcome = "sucesso" if self.success else "falha"
        sign = "+" if self.modifier >= 0 else ""
        return (
            f"🎲 d20({self.die}) {sign}{self.modifier} {attr_label} = "
            f"**{self.total}** vs CD {self.dc} → **{outcome}**{flag}"
        )


def roll_check(modifier: int, dc: int) -> RollResult:
    """Rolagem feita por código — a IA nunca decide o resultado."""
    die = random.randint(1, 20)
    total = die + modifier
    critical = die == 20
    fumble = die == 1
    success = critical or (not fumble and total >= dc)
    return RollResult(die, modifier, total, dc, success, critical, fumble)
