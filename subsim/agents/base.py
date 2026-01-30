"""Agent interface for SubSim."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict

from ..input import Action


class Agent(ABC):
    @abstractmethod
    def reset(self, obs: Dict) -> None:
        raise NotImplementedError

    @abstractmethod
    def act(self, obs: Dict) -> Action:
        raise NotImplementedError


__all__ = ["Agent"]
