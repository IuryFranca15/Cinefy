from pathlib import Path

from analyzer import CinefyInspector


def test_reports_python_syntax_error(tmp_path: Path):
    (tmp_path / "broken.py").write_text("def broken(:\\n    pass\\n", encoding="utf-8")
    inspector = CinefyInspector(tmp_path)
    issues = inspector.scan_codebase()
    assert any(issue.code == "PY_SYNTAX" for issue in issues)


def test_reports_invalid_json(tmp_path: Path):
    (tmp_path / "settings.json").write_text('{"missing": }', encoding="utf-8")
    inspector = CinefyInspector(tmp_path)
    issues = inspector.scan_codebase()
    assert any(issue.code == "JSON_INVALID" for issue in issues)


def test_ignores_virtual_environment(tmp_path: Path):
    venv = tmp_path / ".venv"
    venv.mkdir()
    (venv / "broken.py").write_text("def broken(:", encoding="utf-8")
    inspector = CinefyInspector(tmp_path)
    assert not any(issue.path.startswith(".venv") for issue in inspector.scan_codebase())



def test_scans_streamlit_secrets_and_never_prints_value(tmp_path: Path):
    secrets_dir = tmp_path / ".streamlit"
    secrets_dir.mkdir()
    secret_value = "very-real-client-secret-value"
    (secrets_dir / "secrets.toml").write_text(
        f'[spotify]\nclient_secret = "{secret_value}"\n', encoding="utf-8"
    )
    inspector = CinefyInspector(tmp_path)
    issues = inspector.scan_codebase()
    matches = [issue for issue in issues if issue.code == "POSSIBLE_CREDENTIAL"]
    assert matches
    assert any(issue.path == ".streamlit/secrets.toml" for issue in matches)
    assert secret_value not in "\n".join(issue.message for issue in issues)



def test_detects_unquoted_dotenv_secret(tmp_path: Path):
    (tmp_path / ".env").write_text("TMDB_BEARER_TOKEN=unquoted-secret-token-value\n", encoding="utf-8")
    issues = CinefyInspector(tmp_path).scan_codebase()
    assert any(issue.code == "POSSIBLE_CREDENTIAL" and issue.path == ".env" for issue in issues)
