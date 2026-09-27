"""Inline 'blueprint' SVG diagrams for Anki cards: dark navy grid, colour-coded boxes, arrows.
Each function returns an SVG string (viewBox 960x540, width 100%) that is valid XML."""

BG, PANEL, INK, MUTED, ACCENT, GREEN, ORANGE, RED, PURPLE, GRID = (
    "#0f1b2d", "#182a44", "#e6edf3", "#9fb3c8", "#7dd3fc", "#86efac", "#fdba74", "#fca5a5", "#c4b5fd", "#1c2d47")
FONT = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class SVG:
    def __init__(self, name, title, w=960, h=540):
        self.name, self.w, self.h, self.parts = name, w, h, []
        self.parts.append(f'<rect width="{w}" height="{h}" fill="{BG}"/>'
                          f'<rect width="{w}" height="{h}" fill="url(#grid-{name})"/>')
        self.text(w / 2, 34, title, fs=22, weight="600")

    def text(self, x, y, s, fs=15, fill=INK, anchor="middle", weight="normal", mono=False):
        fam = "Menlo, Consolas, monospace" if mono else FONT
        self.parts.append(f'<text x="{x:.0f}" y="{y:.0f}" font-family="{fam}" font-size="{fs}" fill="{fill}" '
                          f'text-anchor="{anchor}" font-weight="{weight}">{esc(s)}</text>')

    def lines(self, x, y, items, fs=13, fill=MUTED, anchor="middle", lh=17, mono=False):
        for i, s in enumerate(items):
            self.text(x, y + i * lh, s, fs=fs, fill=fill, anchor=anchor, mono=mono)

    def box(self, x, y, w, h, label, sub=None, fill=PANEL, stroke=ACCENT, fs=15, r=8, sub_fs=12, mono_sub=False,
            top=False):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" '
                          f'stroke="{stroke}" stroke-width="1.5"/>')
        cy = y + (22 if (sub or top) else h / 2)
        self.text(x + w / 2, cy + fs / 3, label, fs=fs, weight="600")
        if sub:
            self.lines(x + w / 2, y + 44, sub, fs=sub_fs, mono=mono_sub)

    def group(self, x, y, w, h, title, stroke=MUTED):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="none" stroke="{stroke}" '
                          f'stroke-width="1.2" stroke-dasharray="6 5"/>')
        self.text(x + 12, y + 20, title, fs=13, fill=stroke, anchor="start", weight="600")

    def arrow(self, x1, y1, x2, y2, label=None, color=ACCENT, dashed=False, both=False):
        dash = ' stroke-dasharray="6 5"' if dashed else ""
        start = f' marker-start="url(#dot-{self.name})"' if both else ""
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.8"'
                          f'{dash} marker-end="url(#arrow-{self.name})"{start}/>')
        if label:
            self.text((x1 + x2) / 2, (y1 + y2) / 2 - 10, label, fs=12, fill=color)

    def render(self):
        n = self.name
        defs = (f'<defs><pattern id="grid-{n}" width="24" height="24" patternUnits="userSpaceOnUse">'
                f'<path d="M24 0H0V24" fill="none" stroke="{GRID}" stroke-width="1"/></pattern>'
                f'<marker id="arrow-{n}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" '
                f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#cbd5e1"/></marker>'
                f'<marker id="dot-{n}" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6">'
                f'<circle cx="5" cy="5" r="4" fill="#cbd5e1"/></marker></defs>')
        return (f'<svg xmlns="http://www.w3.org/2000/svg" class="bp" width="100%" viewBox="0 0 {self.w} {self.h}" '
                f'role="img" aria-label="{esc(n)} diagram">{defs}{"".join(self.parts)}</svg>')


def wrap(text, n=20):
    out, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > n:
            out.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return out + [cur]


def arch():
    s = SVG("arch", "Kubernetes cluster architecture")
    s.group(30, 60, 440, 440, "Control plane")
    s.box(60, 100, 110, 44, "kubectl", fill="#243b5e")
    s.box(200, 150, 240, 60, "kube-apiserver", sub=["authn · authz · admission · REST API"])
    s.arrow(170, 122, 250, 150, label="HTTPS")
    s.box(50, 250, 160, 88, "etcd", sub=["cluster state (Raft)", "2379 / 2380", "only apiserver writes it"])
    s.arrow(185, 250, 235, 212, both=True)
    s.box(250, 400, 170, 70, "kube-scheduler", sub=["filter → score → bind"])
    s.arrow(320, 400, 320, 212)
    s.box(60, 400, 160, 70, "kube-controller-", sub=["manager: reconcile loops"])
    s.arrow(200, 400, 270, 212)
    s.group(500, 60, 430, 440, "Worker nodes")
    for i, (x, name) in enumerate([(520, "node-1"), (730, "node-2")]):
        s.box(x, 90, 190, 390, name, fill="#13223a", stroke=MUTED, fs=14, top=True)
        s.box(x + 15, 130, 160, 44, "kubelet", fs=13)
        s.box(x + 15, 190, 160, 44, "kube-proxy", fs=13)
        s.box(x + 15, 250, 160, 44, "container runtime", fs=12)
        s.box(x + 15, 315, 70, 60, "pod", fill="#1f3a5f", stroke=GREEN, fs=12)
        s.box(x + 105, 315, 70, 60, "pod", fill="#1f3a5f", stroke=GREEN, fs=12)
        s.text(x + 95, 410, "pods run here", fs=11, fill=MUTED)
        s.arrow(x + 15, 152, 440, 185, label="watch / report" if i == 0 else None, dashed=True)
    return s.render()


def request_flow():
    s = SVG("reqflow", "What happens to a write request (kubectl apply)")
    s.box(30, 200, 110, 50, "kubectl", fill="#243b5e")
    s.group(160, 90, 620, 270, "kube-apiserver")
    steps = [("Authentication", "who are you?"), ("Authorization", "RBAC: allowed?"),
             ("Mutating admission", "plugins + webhooks may change object"),
             ("Schema validation", "OpenAPI"), ("Validating admission", "plugins + webhooks accept/reject")]
    x = 180
    for i, (t, sub) in enumerate(steps):
        w = 112
        s.box(x, 180, w, 90, t, sub=wrap(sub), fs=12, sub_fs=10)
        if i < len(steps) - 1:
            s.arrow(x + w, 225, x + w + 10, 225)
        x += w + 10
    s.arrow(140, 225, 180, 225)
    s.box(810, 200, 120, 50, "etcd")
    s.arrow(780, 225, 810, 225, label="persist")
    s.box(590, 300, 170, 44, "webhook e.g. Gatekeeper", fill="#2a1f4a", stroke=PURPLE, fs=11)
    s.arrow(675, 270, 675, 300, dashed=True, color=PURPLE)
    s.text(480, 400, "then, asynchronously:", fs=13, fill=MUTED)
    s.box(120, 420, 200, 60, "controllers", sub=["Deployment → ReplicaSet → Pods"], fs=13)
    s.box(380, 420, 200, 60, "kube-scheduler", sub=["binds each pod to a node"], fs=13)
    s.box(640, 420, 200, 60, "kubelet", sub=["pulls image, starts containers"], fs=13)
    s.arrow(320, 450, 380, 450)
    s.arrow(580, 450, 640, 450)
    s.arrow(870, 250, 220, 420, dashed=True, color=MUTED)
    return s.render()


def deployment():
    s = SVG("deploy", "Deployment → ReplicaSet → Pods")
    s.box(330, 70, 300, 70, "Deployment web", sub=["replicas: 3 · template: image v2", "strategy: RollingUpdate"],
          mono_sub=True)
    s.box(120, 220, 260, 70, "ReplicaSet web-5d4f (v1)", sub=["replicas: 0 — kept for rollback"], fs=13,
          stroke=MUTED)
    s.box(580, 220, 260, 70, "ReplicaSet web-7c9b (v2)", sub=["replicas: 3 — current"], fs=13, stroke=GREEN)
    s.arrow(430, 140, 260, 220, label="old", color=MUTED, dashed=True)
    s.arrow(530, 140, 700, 220, label="new template ⇒ new RS")
    for i in range(3):
        s.box(590 + i * 85, 340, 70, 56, "pod", sub=["v2"], fill="#1f3a5f", stroke=GREEN, fs=12, sub_fs=11)
        s.arrow(710, 290, 625 + i * 85, 340, color=GREEN)
    s.text(250, 360, "pods of v1 scaled down", fs=12, fill=MUTED)
    s.lines(480, 450, ["Rolling update: maxSurge = extra pods allowed above desired (25%)",
                       "maxUnavailable = pods allowed down during the update (25%)",
                       "kubectl rollout status | history | undo --to-revision=N"], fs=13, fill=INK, lh=20)
    return s.render()


def service_types():
    s = SVG("svctypes", "Service types")
    cols = [("ClusterIP (default)", "internal virtual IP", None),
            ("NodePort", "node IP : 30000–32767", "Node :30080"),
            ("LoadBalancer", "cloud load balancer", "External IP")]
    for i, (name, sub, top) in enumerate(cols):
        x = 40 + i * 305
        s.group(x, 60, 280, 420, name)
        y = 90
        if top:
            s.box(x + 60, y, 160, 44, top, fill="#2a1f4a", stroke=PURPLE, fs=13)
            s.arrow(x + 140, y + 44, x + 140, y + 74)
            y += 74
        if i == 2:
            s.box(x + 60, y, 160, 44, "Node :30080", fs=13)
            s.arrow(x + 140, y + 44, x + 140, y + 74)
            y += 74
        s.box(x + 40, y, 200, 56, "Service", sub=[sub], fs=13)
        s.arrow(x + 140, y + 56, x + 140, y + 96)
        for j in range(3):
            s.box(x + 20 + j * 85, y + 96, 70, 46, "pod", fill="#1f3a5f", stroke=GREEN, fs=12)
        s.text(x + 140, y + 175, "selected by labels", fs=11, fill=MUTED)
    s.text(480, 500, "DNS: <service>.<namespace>.svc.cluster.local · port → targetPort (container) · "
                     "ExternalName = CNAME only", fs=13, fill=INK)
    return s.render()


def pod_anatomy():
    s = SVG("pod", "Anatomy of a Pod")
    s.box(120, 70, 720, 400, "Pod   IP 10.244.1.7   (one network namespace)", fill="#13223a", stroke=ACCENT, fs=15,
          top=True)
    s.box(150, 130, 180, 90, "init container", sub=["runs first, to", "completion"], fs=13)
    s.arrow(330, 175, 390, 175, label="then")
    s.box(390, 130, 200, 130, "app container", sub=["liveness probe → restart", "readiness probe → traffic",
                                                    "startup probe → wait"], fs=13, sub_fs=11)
    s.box(620, 130, 190, 130, "sidecar container", sub=["log shipper / proxy"], fs=13)
    s.arrow(590, 195, 620, 195, label="localhost", both=True)
    s.box(390, 320, 420, 60, "shared volume (emptyDir / ConfigMap / PVC)", fs=13)
    s.arrow(470, 260, 470, 320, dashed=True)
    s.arrow(720, 260, 720, 320, dashed=True)
    s.lines(480, 430, ["Scale by adding pods, never by adding containers to a pod.",
                       "restartPolicy: Always | OnFailure | Never"], fs=13, fill=INK, lh=20)
    return s.render()


def rbac():
    s = SVG("rbac", "RBAC: who can do what, where")
    s.group(30, 70, 200, 200, "Subjects")
    s.box(50, 100, 160, 40, "User jane", fs=13)
    s.box(50, 150, 160, 40, "Group dev-team", fs=13)
    s.box(50, 200, 160, 40, "ServiceAccount app", fs=12)
    s.group(280, 70, 330, 200, "namespace: dev")
    s.box(300, 110, 130, 50, "RoleBinding", fs=13)
    s.box(460, 110, 130, 50, "Role", sub=["pods: get, list"], fs=13, sub_fs=11)
    s.arrow(430, 135, 460, 135)
    s.arrow(210, 170, 300, 135)
    s.group(280, 300, 330, 150, "cluster-wide")
    s.box(300, 340, 150, 50, "ClusterRoleBinding", fs=12)
    s.box(470, 340, 120, 50, "ClusterRole", sub=["nodes: get"], fs=13, sub_fs=11)
    s.arrow(450, 365, 470, 365)
    s.arrow(210, 175, 300, 365, color=MUTED)
    s.arrow(365, 160, 520, 340, label="RoleBinding → ClusterRole = scoped to dev", dashed=True, color=ORANGE)
    s.box(660, 100, 270, 150, "rule", sub=["apiGroups: [\"\"]", "resources: [pods, pods/log]",
                                          "verbs: [get, list, watch]"], fs=13, mono_sub=True)
    s.lines(795, 320, ["Allow-only, additive — no deny rules.", "kubectl auth can-i <verb> <resource>",
                       "  --as user  -n namespace"], fs=13, fill=INK, lh=20)
    return s.render()


def netpol():
    s = SVG("netpol", "NetworkPolicy: isolate, then allow")
    s.group(40, 70, 560, 380, "namespace: shop")
    s.box(70, 150, 150, 80, "web", sub=["app=web"], fill="#1f3a5f", stroke=GREEN, fs=14)
    s.box(360, 150, 150, 80, "db", sub=["app=db  :5432"], fill="#1f3a5f", stroke=GREEN, fs=14)
    s.box(70, 320, 150, 80, "batch", sub=["app=batch"], fill="#1f3a5f", stroke=MUTED, fs=14)
    s.arrow(220, 190, 360, 190, label="allowed", color=GREEN)
    s.arrow(220, 350, 360, 215, color=RED, dashed=True)
    s.text(300, 300, "denied", fs=12, fill=RED)
    s.box(330, 330, 240, 100, "NetworkPolicy db-ingress", sub=["podSelector: app=db", "policyTypes: [Ingress]",
                                                              "from: podSelector app=web, port 5432"], fs=12,
          sub_fs=11, mono_sub=True)
    s.lines(780, 110, ["No policy selects a pod → all traffic allowed",
                       "A policy selects it → that direction is",
                       "deny-by-default; allows are additive (union)", "", "from:",
                       "- namespaceSelector: …   ← OR (two items)", "- podSelector: …", "vs",
                       "- namespaceSelector: …   ← AND (one item)", "  podSelector: …", "",
                       "Egress deny also blocks DNS: allow 53/UDP+TCP", "Needs a CNI that enforces (Calico, Cilium)"],
            fs=12, fill=INK, lh=22)
    return s.render()


def gatekeeper():
    s = SVG("gk", "OPA Gatekeeper in the admission path")
    s.box(40, 200, 150, 60, "kube-apiserver", sub=["validating admission"], fs=13)
    s.box(240, 200, 190, 60, "ValidatingWebhook-", sub=["Configuration → HTTPS"], fs=12)
    s.arrow(190, 230, 240, 230, label="AdmissionReview")
    s.group(470, 70, 460, 420, "Gatekeeper (runs in cluster)")
    s.box(490, 100, 200, 90, "ConstraintTemplate", sub=["Rego violation[] rule", "+ parameter schema"], fs=13,
          sub_fs=11)
    s.box(720, 100, 190, 90, "new CRD kind", sub=["e.g. K8sRequiredLabels"], fs=13, sub_fs=11, stroke=PURPLE)
    s.arrow(690, 145, 720, 145, label="generates")
    s.box(490, 230, 200, 110, "Constraint", sub=["kind: K8sRequiredLabels", "match: kinds, namespaces",
                                                 "parameters: labels: [owner]", "enforcementAction: deny"],
          fs=13, sub_fs=11, mono_sub=True)
    s.arrow(815, 190, 590, 230, dashed=True, color=PURPLE)
    s.box(720, 230, 190, 110, "webhook handler", sub=["evaluates constraints", "→ allowed / denied", "+ msg"],
          fs=13, sub_fs=11)
    s.arrow(430, 230, 720, 260)
    s.box(490, 380, 200, 90, "audit controller", sub=["every 60 s scans existing", "resources"], fs=13, sub_fs=11)
    s.box(720, 380, 190, 90, "status.violations", sub=["on each Constraint"], fs=13, sub_fs=11, stroke=ORANGE)
    s.arrow(690, 425, 720, 425)
    s.lines(215, 330, ["enforcementAction:", "deny · dryrun · warn", "", "failurePolicy default: Ignore",
                       "(down ⇒ requests allowed)"], fs=12, fill=INK, lh=20)
    return s.render()


def qos():
    s = SVG("qos", "Requests, limits and QoS classes")
    cols = [("Guaranteed", "requests == limits", "for CPU and memory in every container", GREEN),
            ("Burstable", "some requests/limits", "requests < limits, or partial", ORANGE),
            ("BestEffort", "nothing set", "evicted first under pressure", RED)]
    for i, (name, a, b, col) in enumerate(cols):
        x = 40 + i * 305
        s.box(x, 80, 280, 120, name, sub=[a, b], fs=15, stroke=col)
    s.arrow(900, 230, 60, 230, label="eviction order under node pressure", color=RED)
    s.box(60, 290, 400, 180, "requests", sub=["used by the scheduler to place the pod", "reserved on the node",
                                              "cpu: 250m   memory: 128Mi"], fs=15, sub_fs=13, stroke=ACCENT)
    s.box(500, 290, 400, 180, "limits", sub=["enforced at runtime by the kubelet/runtime",
                                             "CPU over limit → throttled", "memory over limit → OOMKilled",
                                             "cpu: 500m   memory: 256Mi"], fs=15, sub_fs=13, stroke=ORANGE)
    s.text(480, 505, "Mi/Gi = binary (2^20, 2^30)   M/G = decimal   1000m = 1 CPU core", fs=13, fill=MUTED)
    return s.render()


def helm():
    s = SVG("helm", "Helm: chart → release")
    s.box(40, 80, 260, 200, "chart  my-app/", sub=["Chart.yaml", "values.yaml", "templates/*.yaml",
                                                     "templates/_helpers.tpl", "charts/ (dependencies)"],
          fs=14, sub_fs=12, mono_sub=True)
    s.box(360, 120, 240, 90, "helm upgrade --install", sub=["my-app ./my-app -n prod",
                                                             "-f prod-values.yaml --set image.tag=1.4"],
          fs=13, sub_fs=11, mono_sub=True)
    s.arrow(300, 180, 360, 165, label="render (Go templates)")
    s.box(660, 120, 260, 90, "rendered manifests", sub=["Deployment, Service, …", "applied via the API server"],
          fs=13, sub_fs=11)
    s.arrow(600, 165, 660, 165)
    s.box(360, 300, 560, 120, "release my-app (namespace prod)",
          sub=["history stored as Secrets: rev 1 → rev 2 → rev 3",
               "helm rollback my-app 2   ·   helm history / list / uninstall"], fs=13, sub_fs=12, mono_sub=True)
    s.arrow(790, 210, 640, 300, dashed=True)
    s.text(480, 480, "helm template renders locally · helm lint checks the chart · Helm 3 has no Tiller",
           fs=13, fill=MUTED)
    return s.render()


def config():
    s = SVG("config", "ConfigMap and Secret → Pod")
    s.box(40, 100, 260, 130, "ConfigMap app-config", sub=["data:", "  LOG_LEVEL: debug", "  config.yaml: |…"],
          fs=13, sub_fs=12, mono_sub=True)
    s.box(40, 280, 260, 130, "Secret db-creds", sub=["data (base64, not encrypted):", "  password: czNjcmV0",
                                                     "type: Opaque | kubernetes.io/tls"], fs=13, sub_fs=11,
          mono_sub=True)
    s.box(420, 80, 500, 380, "Pod", fill="#13223a", stroke=ACCENT, fs=15, top=True)
    s.box(450, 130, 440, 80, "env vars", sub=["envFrom.configMapRef / valueFrom.secretKeyRef",
                                              "fixed at start — restart pod to pick up changes"], fs=13, sub_fs=11)
    s.box(450, 240, 440, 80, "volume files", sub=["/etc/config/LOG_LEVEL   /etc/secrets/password",
                                                  "refreshed by kubelet (not subPath)"], fs=13, sub_fs=11)
    s.box(450, 350, 440, 80, "imagePullSecrets", sub=["kubernetes.io/dockerconfigjson secret for registries"],
          fs=13, sub_fs=11)
    s.arrow(300, 165, 450, 170)
    s.arrow(300, 200, 450, 280)
    s.arrow(300, 345, 450, 300, color=ORANGE)
    s.arrow(300, 380, 450, 390, color=ORANGE)
    s.text(480, 500, "ConfigMap limit 1 MiB · immutable: true · Secret volumes are tmpfs · enable encryption at rest",
           fs=12, fill=MUTED)
    return s.render()


def namespaces():
    s = SVG("ns", "Namespaces: namespaced vs cluster-scoped")
    s.group(40, 70, 600, 400, "cluster")
    for i, (name, items) in enumerate([("default", ["pods, services", "deployments"]),
                                       ("dev", ["ResourceQuota", "LimitRange", "Roles, RoleBindings",
                                                "NetworkPolicies", "ConfigMaps, Secrets"]),
                                       ("kube-system", ["coredns, kube-proxy", "control-plane pods"])]):
        x = 60 + i * 195
        s.box(x, 110, 175, 330, "ns: " + name, sub=items, fs=13, sub_fs=12)
    s.box(670, 110, 250, 330, "cluster-scoped", sub=["Nodes", "PersistentVolumes", "StorageClasses",
                                                     "ClusterRoles / Bindings", "Namespaces themselves",
                                                     "CustomResourceDefinitions", "", "kubectl api-resources",
                                                     "  --namespaced=false"], fs=14, sub_fs=12, stroke=ORANGE)
    s.text(480, 500, "kubectl -n dev · -A · kubectl config set-context --current --namespace=dev", fs=13,
           fill=MUTED)
    return s.render()


def scheduler():
    s = SVG("sched", "How the scheduler places a pod")
    s.box(40, 200, 150, 70, "Pending pod", sub=["nodeName: (none)", "requests: 500m/256Mi"], fs=13, sub_fs=11,
          mono_sub=True)
    s.box(240, 120, 200, 230, "1. Filter", sub=["enough free requests?", "taints tolerated?", "nodeSelector /",
                                                "node affinity match?", "ports & volumes ok?"], fs=15, sub_fs=12)
    s.box(490, 120, 200, 230, "2. Score", sub=["spread across nodes/zones", "resource balance",
                                               "preferred affinity weights", "image locality"], fs=15, sub_fs=12)
    s.box(740, 200, 180, 70, "3. Bind", sub=["sets pod.spec.nodeName"], fs=15, sub_fs=11)
    s.arrow(190, 235, 240, 235)
    s.arrow(440, 235, 490, 235, label="candidates")
    s.arrow(690, 235, 740, 235, label="best node")
    s.text(480, 420, "kubelet on that node then pulls the image and starts the containers", fs=13, fill=INK)
    s.text(480, 460, "Pending forever? kubectl describe pod → Events shows which filter failed", fs=13, fill=MUTED)
    return s.render()


def securitycontext():
    s = SVG("secctx", "securityContext: pod level vs container level")
    s.box(40, 80, 420, 380, "pod.spec.securityContext", sub=["applies to all containers + volumes", "",
                                                             "runAsUser / runAsGroup", "runAsNonRoot: true",
                                                             "fsGroup (volume ownership)", "supplementalGroups",
                                                             "seccompProfile: RuntimeDefault", "sysctls"],
          fs=14, sub_fs=13, mono_sub=True)
    s.box(500, 80, 420, 380, "container.securityContext",
          sub=["overrides pod level for that container", "", "privileged: false",
               "allowPrivilegeEscalation: false", "readOnlyRootFilesystem: true", "capabilities: drop: [ALL]",
               "  add: [NET_BIND_SERVICE]", "runAsUser / runAsNonRoot (override)"],
          fs=14, sub_fs=13, mono_sub=True, stroke=ORANGE)
    s.text(480, 500, "Cluster-wide baseline: Pod Security Admission labels (privileged / baseline / restricted)",
           fs=13, fill=MUTED)
    return s.render()


def ingress_vs_lb():
    s = SVG("ingress", "Ingress vs LoadBalancer Services")
    s.group(40, 70, 400, 420, "One LoadBalancer Service per app")
    for i, name in enumerate(["shop", "blog", "api"]):
        y = 110 + i * 120
        s.box(60, y, 130, 50, f"cloud LB {i + 1}", fill="#2a1f4a", stroke=PURPLE, fs=12)
        s.box(260, y, 150, 50, f"Service {name}", sub=None, fs=12, stroke=GREEN)
        s.arrow(190, y + 25, 260, y + 25)
    s.text(240, 470, "3 apps = 3 load balancers, L4 only", fs=12, fill=MUTED)
    s.group(500, 70, 430, 420, "One Ingress in front of many Services")
    s.box(520, 110, 130, 50, "cloud LB", fill="#2a1f4a", stroke=PURPLE, fs=12)
    s.box(690, 100, 220, 70, "Ingress controller", sub=["host / path rules · TLS"], fs=12, sub_fs=11)
    s.arrow(650, 135, 690, 135)
    for i, (rule, name) in enumerate([("shop.example.com", "shop"), ("blog.example.com", "blog"),
                                      ("example.com/api", "api")]):
        y = 230 + i * 80
        s.box(700, y, 200, 50, f"Service {name}", sub=[rule], fs=12, sub_fs=10, stroke=GREEN)
        s.arrow(800, 170, 800, y, color=GREEN)
    s.text(715, 470, "1 load balancer, L7 routing (HTTP/HTTPS)", fs=12, fill=MUTED)
    return s.render()


def cordon_drain():
    s = SVG("drain", "Node maintenance: cordon → drain → uncordon")
    steps = [("kubectl cordon node-1", "SchedulingDisabled:", "no new pods land here", ACCENT),
             ("kubectl drain node-1", "--ignore-daemonsets", "--delete-emptydir-data", ORANGE),
             ("maintenance", "reboot, upgrade kubelet,", "patch the OS…", MUTED),
             ("kubectl uncordon node-1", "schedulable again;", "pods are not moved back", GREEN)]
    for i, (t, a, b, col) in enumerate(steps):
        x = 40 + i * 232
        s.box(x, 150, 200, 110, t, sub=[a, b], fs=12, sub_fs=11, stroke=col)
        if i < 3:
            s.arrow(x + 200, 205, x + 232, 205)
    s.lines(480, 340, ["drain evicts pods gracefully (honouring PodDisruptionBudgets) so controllers",
                       "recreate them on other nodes; DaemonSet pods stay, bare pods need --force"],
            fs=13, fill=INK, lh=20)
    return s.render()


def scheduler_watch():
    s = SVG("schedwatch", "How the scheduler finds work")
    s.box(60, 210, 200, 80, "kube-apiserver", sub=["pods with nodeName: (none)"], fs=14, sub_fs=11)
    s.box(560, 210, 220, 80, "kube-scheduler", sub=["picks a node, writes a Binding"], fs=14, sub_fs=11)
    s.arrow(560, 235, 260, 235, label="watch: new unscheduled pod?", dashed=True)
    s.arrow(260, 270, 560, 270, label="bind pod → node", color=GREEN)
    s.lines(480, 400, ["The API server never calls the scheduler — the scheduler pulls work by watching.",
                       "Same pattern for controllers and the kubelet."], fs=13, fill=INK, lh=20)
    return s.render()


def probes():
    s = SVG("probes", "Container probes")
    cols = [("startup", "gates the other probes until", "a slow app has started", ACCENT),
            ("readiness", "failing ⇒ pod removed from", "Service endpoints (no traffic)", GREEN),
            ("liveness", "failing ⇒ container is", "restarted", ORANGE)]
    for i, (t, a, b, col) in enumerate(cols):
        x = 40 + i * 305
        s.box(x, 110, 280, 130, f"{t} probe", sub=[a, b], fs=15, sub_fs=12, stroke=col)
    s.arrow(320, 175, 345, 175)
    s.arrow(625, 175, 650, 175)
    s.lines(480, 330, ["handlers: httpGet · tcpSocket · exec · grpc",
                       "tuning: initialDelaySeconds · periodSeconds · failureThreshold"], fs=13, fill=INK, lh=22)
    return s.render()


DIAGRAMS = {
    "arch": arch, "request-flow": request_flow, "deployment": deployment, "service-types": service_types,
    "pod-anatomy": pod_anatomy, "rbac": rbac, "netpol": netpol, "gatekeeper": gatekeeper, "qos": qos,
    "helm": helm, "config": config, "namespaces": namespaces, "scheduler": scheduler,
    "securitycontext": securitycontext, "ingress-vs-lb": ingress_vs_lb, "cordon-drain": cordon_drain,
    "scheduler-watch": scheduler_watch, "probes": probes,
}


def svg(name):
    return DIAGRAMS[name]()
