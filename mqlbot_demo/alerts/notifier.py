"""Notification back-ends. The demo prints messages instead of calling a messenger API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class Notifier(Protocol):
    def send(self, recipient: str, subject: str, contents: str) -> bool:
        """Return True when the message was accepted for delivery."""


@dataclass
class SentMessage:
    recipient: str
    subject: str
    contents: str


@dataclass
class ConsoleNotifier:
    verbose: bool = True
    sent: list[SentMessage] = field(default_factory=list)

    def send(self, recipient: str, subject: str, contents: str) -> bool:
        self.sent.append(SentMessage(recipient, subject, contents))
        if self.verbose:
            print(f"\n📨 To: {recipient}\n{contents}")
        return True
