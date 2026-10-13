# MyOTA test deployment

This Fleet bundle deploys the shared MyOTA chart into `myota-test` using the
mutable GHCR `testing` tags. The chart digest file records the resolved image
digests, so a changed tag changes the pod template and causes a Kubernetes
rollout. The scheduled digest workflow proposes each update as a PR to the
protected `testing` branch and dispatches the required checks before enabling
auto-merge.

The test namespace owns independent PostgreSQL databases, JetStream, SeaweedFS,
and observability storage. Application workloads do not point at the live
namespace. Test secrets use distinct credentials and token-signing keys;
location enrichment and production load-test cleanup are disabled.

## First deployment sequence

1. Create the `myota-test` namespace and its runtime Secrets from local
   `runtime-secrets` files. Never copy the live auth signing key, PostgreSQL
   credentials, or S3 credentials into this namespace.
2. Add a Fleet `GitRepo` targeting branch `testing` and path
   `deploy/helm/myota-test`. The committed values deliberately keep ingress
   disabled until the one-time data copy completes.
3. Wait for the test release's three database StatefulSets, migration Job,
   SeaweedFS, and NATS to become ready. Confirm all three test databases are
   independent from the services in namespace `myota`.
4. Copy current relational domain data from the live databases into the
   migrated test databases. Preserve the target migration ledger, seeded
   PostGIS reference tables, and `entity_type` catalog. Do not copy outbox
   delivery state, JetStream messages, consumer checkpoints, sessions,
   recovery tokens, or observability data; those are environment-specific and
   JetStream is not the durable domain archive.
5. Copy the live application buckets (`myota-award-assets`,
   `myota-award-signatures`, `myota-certificates`, `myota-adif`, and
   `myota-geodata-imports`) into test SeaweedFS. Do not copy Loki objects.
   Verify object counts and bytes before exposing the test hostnames.
6. Enable test ingress through a change to `values-testing.yaml` merged into
   the protected `testing` branch.
   Fleet then publishes `api.test.myota.top`, `admin.test.myota.top`, and
   `test.myota.top`; the participant Web UI routes `/v1` to the test API
   gateway and other paths to the test Web deployment.
7. Verify ACME certificates, admin login, participant UI, API reads, object
   reads, and that no test pod connects to a live namespace endpoint.

The copy is a one-time initial seed, not continuous production-to-test
replication. Keep source credentials out of the test namespace after the copy.
The test deployment uses its own empty JetStream streams; do not replay live
messages into it.

### One-time copy commands

Run these only after Fleet has installed the release with ingress disabled and
all target migrations are complete:

```sh
bash scripts/copy-live-data-to-test.sh

kubectl get secret myota-s3-auth -n myota -o json \
  | jq '.metadata.name = "myota-live-copy-source"
        | .metadata.namespace = "myota-test"
        | del(.metadata.uid, .metadata.resourceVersion,
              .metadata.creationTimestamp, .metadata.managedFields,
              .metadata.ownerReferences)' \
  | kubectl apply -f -

kubectl create configmap myota-test-object-copy \
  -n myota-test \
  --from-file=copy-live-object-data.py=scripts/copy-live-object-data.py
```

Create the temporary object-copy Job with the test Geodata image and these
environment values (the credentials are Secret references, never literals):

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: myota-test-object-copy
  namespace: myota-test
spec:
  backoffLimit: 1
  activeDeadlineSeconds: 900
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: copy
          image: ghcr.io/myota-platform/myota-geodata-service:testing
          imagePullPolicy: Always
          command: [python3, /copy/copy-live-object-data.py]
          env:
            - {name: LIVE_S3_ENDPOINT, value: "http://myota-seaweedfs.myota.svc.cluster.local:8333"}
            - {name: TEST_S3_ENDPOINT, value: "http://myota-seaweedfs.myota-test.svc.cluster.local:8333"}
            - name: LIVE_S3_ACCESS_KEY
              valueFrom: {secretKeyRef: {name: myota-live-copy-source, key: access-key}}
            - name: LIVE_S3_SECRET_KEY
              valueFrom: {secretKeyRef: {name: myota-live-copy-source, key: secret-key}}
            - name: AWS_ACCESS_KEY_ID
              valueFrom: {secretKeyRef: {name: myota-s3-auth, key: access-key}}
            - name: AWS_SECRET_ACCESS_KEY
              valueFrom: {secretKeyRef: {name: myota-s3-auth, key: secret-key}}
          volumeMounts:
            - {name: script, mountPath: /copy, readOnly: true}
      volumes:
        - name: script
          configMap: {name: myota-test-object-copy}
```

Apply the Job, wait for completion, and inspect only its bucket-level count
output. Then remove `myota-test-object-copy`, `myota-test-object-copy` Job,
and `myota-live-copy-source` Secret. The relational copy script refuses to
seed if the live database contains user accounts; add an anonymization step
before copying identity data if that guard ever trips.

## Runtime requirements

The test image digest workflow runs from the default branch every five minutes.
It checks GHCR `testing` tags for the platform runtime, gateway, Identity,
Programme, Geodata, Activity, Admin Web, and Web images. For a changed digest,
it opens or updates a PR to `testing`, dispatches the branch's Python, runtime
image, and Helm checks, and enables auto-merge subject to branch protection.
Fleet watches `testing` and reconciles the resulting digest change. A failed
check leaves the PR open and the currently deployed image unchanged.

Production values remain in `deploy/helm/myota`; this wrapper is a separate
Helm release and leaves the production namespace and PVCs untouched.
