{{/* Common labels. Selectors use only app.kubernetes.io/name, matching the kustomize base. */}}
{{- define "keh.labels" -}}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/part-of: kubeestatehub
app.kubernetes.io/instance: {{ .ctx.Release.Name }}
app.kubernetes.io/managed-by: {{ .ctx.Release.Service }}
app.kubernetes.io/environment: {{ .ctx.Values.environment }}
helm.sh/chart: {{ printf "%s-%s" .ctx.Chart.Name .ctx.Chart.Version | replace "+" "_" }}
{{- with .component }}
app.kubernetes.io/component: {{ . }}
{{- end }}
{{- end }}

{{- define "keh.podLabels" -}}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/part-of: kubeestatehub
{{- with .component }}
app.kubernetes.io/component: {{ . }}
{{- end }}
{{- end }}

{{/* Image reference for a first-party service. */}}
{{- define "keh.image" -}}
{{- printf "%s/%s:%s" .ctx.Values.global.imageRegistry .name (default .ctx.Chart.AppVersion .ctx.Values.global.imageTag) -}}
{{- end }}

{{- define "keh.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: {{ .uid }}
runAsGroup: {{ .uid }}
{{- if .fsGroup }}
fsGroup: {{ .uid }}
{{- end }}
seccompProfile: {type: RuntimeDefault}
{{- end }}

{{- define "keh.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities: {drop: [ALL]}
{{- end }}

{{- define "keh.dbEnv" -}}
- name: DATABASE_URL
  valueFrom: {secretKeyRef: {name: db-secret, key: database-url}}
{{- end }}

{{- define "keh.pgEnv" -}}
- {name: PGHOST, value: postgres}
- {name: PGDATABASE, value: kubeestatehub}
- name: PGUSER
  valueFrom: {secretKeyRef: {name: db-secret, key: username}}
- name: PGPASSWORD
  valueFrom: {secretKeyRef: {name: db-secret, key: password}}
{{- end }}

{{/* Fail early on unusable value combinations. */}}
{{- define "keh.validate" -}}
{{- if and .Values.secrets.create .Values.externalSecrets.enabled -}}
{{- fail "secrets.create and externalSecrets.enabled are mutually exclusive" -}}
{{- end -}}
{{- if .Values.secrets.create -}}
{{- if or (not .Values.secrets.dbPassword) (not .Values.secrets.writeToken) -}}
{{- fail "secrets.create=true requires secrets.dbPassword and secrets.writeToken" -}}
{{- end -}}
{{- end -}}
{{- end }}
