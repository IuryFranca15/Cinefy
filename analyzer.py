#!/usr/bin/env python3
"""Auditoria estática do projeto Cinefy.

Uso:
    python analyzer.py
    python analyzer.py --path . --format json
    python analyzer.py --strict
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_IGNORES = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    "build", "dist", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".idea", ".vscode", "site-packages",
}
TEXT_SUFFIXES = {".py", ".json", ".toml", ".ini", ".cfg", ".yaml", ".yml", ".env"}
SECRET_PATTERNS = [
    re.compile(r"""(?i)(?:^|[^A-Za-z0-9])(?:[A-Za-z0-9]+_)*(?:client_secret|api_key|bearer_token|access_token|refresh_token|secret_key|password|token)\b["']?\s*[:=]\s*(?:"([^"]{8,})"|'([^']{8,})')"""),
    re.compile(r"""(?i)\bsk-[A-Za-z0-9_-]{20,}\b"""),
    re.compile(r"""(?i)\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"""),
]
ENV_SECRET_PATTERN = re.compile(
    r"""(?i)^\s*(?:[A-Za-z0-9]+_)*(?:client_secret|api_key|bearer_token|access_token|refresh_token|secret_key|password|token)\s*=\s*([^\s#]{8,})\s*$"""
)

PLACEHOLDERS = ("your_", "seu_", "changeme", "example", "placeholder", "xxx", "****", "replace_me", "<")


def _effective_suffix(path: Path) -> str:
    """Extensão real do arquivo; modelos como `secrets.toml.example` contam como `.toml`."""
    suffix = path.suffix.lower()
    if suffix in {".example", ".sample", ".template"}:
        return Path(path.stem).suffix.lower()
    return suffix


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    path: str
    line: int | None
    message: str

    def __str__(self) -> str:
        location = f"{self.path}:{self.line}" if self.line else self.path
        return f"[{self.severity}] {self.code} {location} — {self.message}"


class CinefyInspector:
    """Executa verificações estáticas sem importar nem executar o código auditado."""

    def __init__(
        self,
        project_path: str | os.PathLike[str] = ".",
        *,
        ignores: Iterable[str] | None = None,
        max_file_size: int = 2_000_000,
    ) -> None:
        self.project_path = Path(project_path).expanduser().resolve()
        self.ignores = set(ignores or DEFAULT_IGNORES)
        self.max_file_size = max_file_size
        self.issues: list[Issue] = []

    def _add(self, severity: str, code: str, path: Path, message: str, line: int | None = None) -> None:
        try:
            display = str(path.relative_to(self.project_path))
        except ValueError:
            display = str(path)
        self.issues.append(Issue(severity, code, display, line, message))

    def _iter_files(self) -> Iterable[Path]:
        for current, dirs, filenames in os.walk(self.project_path):
            # .streamlit is intentionally inspected because it commonly stores
            # secrets.toml. Other hidden folders remain excluded unless explicitly
            # configured otherwise.
            dirs[:] = sorted(
                d for d in dirs
                if d not in self.ignores and (not d.startswith(".") or d == ".streamlit")
            )
            for filename in sorted(filenames):
                path = Path(current) / filename
                if path.is_symlink() or path.name == "analyzer.py":
                    continue
                if _effective_suffix(path) in TEXT_SUFFIXES or path.name == ".env" or path.name.startswith(".env."):
                    yield path

    def scan_codebase(self) -> list[Issue]:
        self.issues = []
        if not self.project_path.exists():
            self._add("ERROR", "PATH_NOT_FOUND", self.project_path, "Diretório informado não existe.")
            return self.issues
        if not self.project_path.is_dir():
            self._add("ERROR", "NOT_A_DIRECTORY", self.project_path, "O caminho informado não é uma pasta.")
            return self.issues

        for path in self._iter_files():
            try:
                if path.stat().st_size > self.max_file_size:
                    self._add("WARNING", "FILE_TOO_LARGE", path, "Arquivo ignorado por exceder o limite de leitura.")
                    continue
                content = path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                self._add("WARNING", "ENCODING", path, "Não foi possível ler como UTF-8; arquivo ignorado.")
                continue
            except OSError as exc:
                self._add("ERROR", "READ_ERROR", path, f"Falha ao ler arquivo: {exc}")
                continue

            suffix = _effective_suffix(path)
            if suffix == ".py":
                self._audit_python(path, content)
            elif suffix == ".json":
                self._audit_json(path, content)
            elif suffix == ".toml":
                self._audit_toml(path, content)
            if suffix in {".py", ".toml", ".ini", ".cfg", ".yaml", ".yml", ".env", ".json"} or path.name == ".env" or path.name.startswith(".env."):
                self._audit_secrets(path, content)
        self._audit_project_conventions()
        return sorted(self.issues, key=lambda item: ({"ERROR": 0, "WARNING": 1, "INFO": 2}.get(item.severity, 3), item.path, item.line or 0))

    def _audit_python(self, path: Path, content: str) -> None:
        try:
            tree = ast.parse(content, filename=str(path))
        except SyntaxError as exc:
            self._add("ERROR", "PY_SYNTAX", path, exc.msg, exc.lineno)
            return

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body = node.body
                meaningful = [n for n in body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str))]
                if len(meaningful) == 1 and isinstance(meaningful[0], ast.Pass):
                    self._add("WARNING", "EMPTY_FUNCTION", path, f"A função '{node.name}' contém apenas pass.", node.lineno)
                elif len(meaningful) == 1 and isinstance(meaningful[0], ast.Expr) and isinstance(meaningful[0].value, ast.Constant) and meaningful[0].value.value is Ellipsis:
                    self._add("WARNING", "EMPTY_FUNCTION", path, f"A função '{node.name}' contém apenas reticências.", node.lineno)

            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "eval":
                self._add("WARNING", "DYNAMIC_EVAL", path, "Uso de eval() pode executar código arbitrário.", node.lineno)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "exec":
                self._add("WARNING", "DYNAMIC_EXEC", path, "Uso de exec() dificulta auditoria e pode executar código arbitrário.", node.lineno)

    def _audit_secrets(self, path: Path, content: str) -> None:
        for lineno, line in enumerate(content.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            matches = [pattern.search(line) for pattern in SECRET_PATTERNS]
            if path.name == ".env" or path.name.startswith(".env."):
                matches.append(ENV_SECRET_PATTERN.search(line))
            for match in matches:
                if not match:
                    continue
                value = next((group for group in match.groups() if group), match.group(0))
                lowered = value.strip().lower()
                if lowered and not any(word in lowered for word in PLACEHOLDERS):
                    # Never include the detected value in the issue message.
                    self._add(
                        "WARNING",
                        "POSSIBLE_CREDENTIAL",
                        path,
                        "Possível credencial literal detectada. Preserve-a apenas em ambiente privado e nunca publique este arquivo.",
                        lineno,
                    )
                break

    def _audit_json(self, path: Path, content: str) -> None:
        try:
            json.loads(content)
        except json.JSONDecodeError as exc:
            self._add("ERROR", "JSON_INVALID", path, f"{exc.msg} (linha {exc.lineno}, coluna {exc.colno}).", exc.lineno)

    def _audit_toml(self, path: Path, content: str) -> None:
        try:
            tomllib.loads(content)
        except tomllib.TOMLDecodeError as exc:
            self._add("ERROR", "TOML_INVALID", path, str(exc))

    def _audit_project_conventions(self) -> None:
        requirements = self.project_path / "requirements.txt"
        if not requirements.exists():
            self._add("WARNING", "NO_REQUIREMENTS", requirements, "Não encontrei requirements.txt.")
        readme = self.project_path / "README.md"
        if not readme.exists():
            self._add("WARNING", "NO_README", readme, "Não encontrei README.md.")
        gitignore = self.project_path / ".gitignore"
        if gitignore.exists():
            try:
                rules = gitignore.read_text(encoding="utf-8").lower()
                for sensitive in (".streamlit/secrets.toml", ".env", "*.db"):
                    if sensitive not in rules:
                        self._add("WARNING", "GITIGNORE_REVIEW", gitignore, f"Considere ignorar '{sensitive}' para evitar publicar segredos ou banco local.")
            except OSError:
                pass

    def summary(self) -> dict[str, int]:
        return {
            "errors": sum(i.severity == "ERROR" for i in self.issues),
            "warnings": sum(i.severity == "WARNING" for i in self.issues),
            "info": sum(i.severity == "INFO" for i in self.issues),
            "total": len(self.issues),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditoria estática do projeto Cinefy.")
    parser.add_argument("--path", default=".", help="Pasta do projeto (padrão: diretório atual).")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Formato do relatório.")
    parser.add_argument("--strict", action="store_true", help="Retorna código 1 também quando houver avisos.")
    args = parser.parse_args()

    inspector = CinefyInspector(args.path)
    issues = inspector.scan_codebase()
    summary = inspector.summary()

    if args.format == "json":
        print(json.dumps({"summary": summary, "issues": [asdict(i) for i in issues]}, ensure_ascii=False, indent=2))
    else:
        print(f"\nCINEFY • AUDITORIA ESTÁTICA\nPasta: {inspector.project_path}\n")
        if issues:
            for issue in issues:
                print(issue)
        else:
            print("Nenhum problema encontrado nas verificações executadas.")
        print(f"\nErros: {summary['errors']} | Avisos: {summary['warnings']} | Total: {summary['total']}")

    return 1 if summary["errors"] or (args.strict and summary["warnings"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
