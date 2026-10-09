import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]


class ObservabilityConfigurationTests(unittest.TestCase):
    def test_all_provisioned_dashboards_have_requested_defaults_and_match_helm(
        self,
    ):
        for source in (ROOT / "observability/grafana/dashboards").glob(
            "*.json"
        ):
            dashboard = json.loads(source.read_text())
            mirror = (
                ROOT
                / "deploy/helm/myota/observability/grafana/dashboards"
                / source.name
            )
            self.assertEqual(dashboard, json.loads(mirror.read_text()))
            self.assertEqual(
                dashboard["time"], {"from": "now-30m", "to": "now"}
            )
            self.assertEqual(dashboard["refresh"], "30s")
            self.assertEqual(dashboard["timezone"], "utc")
            self.assertTrue(dashboard["editable"])

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

    def test_seaweed_dashboard_is_valid_and_rolls_out_with_helm(self):
        dashboard_path = (
            ROOT
            / "observability"
            / "grafana"
            / "dashboards"
            / "myota-object-storage.json"
        )
        chart_dashboard_path = (
            ROOT
            / "deploy"
            / "helm"
            / "myota"
            / "observability"
            / "grafana"
            / "dashboards"
            / "myota-object-storage.json"
        )
        dashboard = json.loads(dashboard_path.read_text())
        chart_dashboard = json.loads(chart_dashboard_path.read_text())
        deployment_template = (
            ROOT
            / "deploy"
            / "helm"
            / "myota"
            / "templates"
            / "observability.yaml"
        ).read_text()

        self.assertEqual(dashboard, chart_dashboard)
        self.assertEqual("myota-object-storage", dashboard["uid"])
        self.assertGreater(len(dashboard["panels"]), 0)
        self.assertIn("checksum/grafana-config:", deployment_template)
        self.assertIn(
            '.Files.Glob "observability/grafana/**"', deployment_template
        )


if __name__ == "__main__":
    unittest.main()
