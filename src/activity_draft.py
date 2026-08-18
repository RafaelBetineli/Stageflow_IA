"""Tipos neutros compartilhados pela composicao e validacao de atividades."""

from dataclasses import dataclass


class ActivityCompositionError(RuntimeError):
    """Erro base da composicao deterministica de uma atividade."""


@dataclass(frozen=True)
class StructuredDraft:
    """Rascunho composto por paragrafos identificados pelo plano narrativo."""

    paragraphs: tuple[tuple[str, str], ...]

    @property
    def text(self) -> str:
        return "\n\n".join(text for _, text in self.paragraphs)

    def get(self, key: str) -> str:
        for paragraph_key, text in self.paragraphs:
            if paragraph_key == key:
                return text
        raise KeyError(key)
