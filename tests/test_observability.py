import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]


class ObservabilityConfigurationTests(unittest.TestCase):
    def test_prometheus_uses_collector_boundary(self):
        config = (ROOT / "observability" / "prometheus.yml").read_text()
        self.assertIn("otel-collector:8889", config)
        self.assertNotIn("identity:8001", config)
        self.assertNotIn("geodata:8003", config)

    def test_collector_has_otlp_and_prometheus_pipelines(self):
        config = (ROOT / "observability" / "otel-collector.yaml").read_text()
        self.assertIn("otlp:", config)
        self.assertIn("prometheus:", config)
        self.assertIn("otlp/tempo", config)
        self.assertIn("endpoint: 0.0.0.0:8889", config)

    def test_dashboard_is_real_data_only(self):
        dashboard = json.loads(
            (
                ROOT
                / "observability"
                / "grafana"
                / "dashboards"
                / "myota-operations.json"
            ).read_text()
        )
        expressions = [
            target.get("expr", "")
            for panel in dashboard["panels"]
            for target in panel.get("targets", [])
        ]
        self.assertTrue(
            any(
                "myota_identity_users_total" in expression
                for expression in expressions
            )
        )
        self.assertTrue(
            any(
                "myota_geodata_entities_total" in expression
                for expression in expressions
            )
        )
        self.assertTrue(
            any(
                "myota_activity_qsos_total" in expression
                for expression in expressions
            )
        )
        self.assertTrue(
            any(
                "myota_http_server_requests_total" in expression
                for expression in expressions
            )
        )
        self.assertFalse(
            any(
                "vector(1)" in expression or "count(up)" in expression
                for expression in expressions
            )
        )


if __name__ == "__main__":
    unittest.main()
