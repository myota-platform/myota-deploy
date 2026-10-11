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


    def test_loki_uses_s3_retention_and_native_otlp_pipeline(self):
        compose_config = (ROOT / "observability" / "loki.yaml").read_text()
        helm_config = (
            ROOT / "deploy/helm/myota/observability/loki.yaml"
        ).read_text()
        compose_collector = (
            ROOT / "observability" / "otel-collector.yaml"
        ).read_text()
        helm_collector = (
            ROOT / "deploy/helm/myota/observability/otel-collector.yaml"
        ).read_text()
        helm_template = (
            ROOT / "deploy/helm/myota/templates/observability.yaml"
        ).read_text()
        compose = (ROOT / "compose.yaml").read_text()

        for config in (compose_config, helm_config):
            self.assertIn("store: tsdb", config)
            self.assertIn("object_store: s3", config)
            self.assertIn("retention_enabled: true", config)
            self.assertIn("delete_request_store: s3", config)
            self.assertIn("ignore_defaults: true", config)
            self.assertIn("service.namespace", config)
        self.assertIn("bucketnames: myota-loki", compose_config)
        self.assertIn(".Values.observability.loki.bucketName", helm_config)
        self.assertIn("retention_period: 336h", compose_config)
        self.assertIn(".Values.observability.loki.retentionPeriod", helm_config)
        self.assertIn("endpoint: http://loki:3100/otlp", compose_collector)
        self.assertIn("endpoint: http://myota-loki:3100/otlp", helm_collector)
        self.assertIn("exporters: [otlphttp/loki]", helm_collector)
        self.assertIn("loki-data", helm_template)
        self.assertIn("workingStorageSize", helm_template)
        self.assertIn("loki-bucket-init", compose)
        self.assertIn("loki:3100", compose)
        self.assertIn("loki-data:", compose)


if __name__ == "__main__":
    unittest.main()
