import io

from scripts import run_scheduled_backup


def test_scheduled_backup_requires_configuration(monkeypatch, capsys):
    monkeypatch.delenv("THERMAL_BACKUP_TRIGGER_URL", raising=False)
    monkeypatch.delenv("THERMAL_SAAS_ADMIN_TOKEN", raising=False)

    assert run_scheduled_backup.main() == 2
    assert "are required" in capsys.readouterr().err


def test_scheduled_backup_calls_endpoint(monkeypatch, capsys):
    monkeypatch.setenv(
        "THERMAL_BACKUP_TRIGGER_URL",
        "https://example.test/admin/backups",
    )
    monkeypatch.setenv("THERMAL_SAAS_ADMIN_TOKEN", "secret-token")
    response = io.BytesIO(
        b'{"status":"ok","backup":{"bucket":"backups","key":"daily.sqlite.gz"}}',
    )
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return response

    monkeypatch.setattr(run_scheduled_backup, "urlopen", fake_urlopen)

    assert run_scheduled_backup.main() == 0
    assert captured["request"].full_url == "https://example.test/admin/backups"
    assert captured["request"].get_header("X-thermal-admin-token") == "secret-token"
    assert captured["timeout"] == 180
    assert "backups daily.sqlite.gz" in capsys.readouterr().out
