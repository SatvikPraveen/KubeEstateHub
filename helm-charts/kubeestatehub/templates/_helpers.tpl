# Location: `/helm-charts/kubeestatehub/templates/_helpers.tpl`

{{/*
Expand the name of the chart.
*/}}
{{- define "kubeestatehub.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "kubeestatehub.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "kubeestatehub.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "kubeestatehub.labels" -}}
helm.sh/chart: {{ include "kubeestatehub.chart" . }}
{{ include "kubeestatehub.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: kubeestatehub
{{- end }}

{{/*
Selector labels
*/}}
{{- define "kubeestatehub.selectorLabels" -}}
app.kubernetes.io/name: {{ include "kubeestatehub.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "kubeestatehub.serviceAccountName" -}}
{{- if .Values.serviceAccounts.create }}
{{- default (include "kubeestatehub.fullname" .) .Values.serviceAccounts.name }}
{{- else }}
{{- default "default" .Values.serviceAccounts.name }}
{{- end }}
{{- end }}

{{/*
Generate certificates for webhook
*/}}
{{- define "kubeestatehub.webhook-certs" -}}
{{- $altNames := list ( printf "%s.%s" (include "kubeestatehub.fullname" .) .Release.Namespace ) ( printf "%s.%s.svc" (include "kubeestatehub.fullname" .) .Release.Namespace ) -}}
{{- $ca := genCA "kubeestatehub-ca" 3650 -}}
{{- $cert := genSignedCert ( include "kubeestatehub.fullname" . ) nil $altNames 3650 $ca -}}
tls.crt: {{ $cert.Cert | b64enc }}
tls.key: {{ $cert.Key | b64enc }}
ca.crt: {{ $ca.Cert | b64enc }}
{{- end }}

{{/*
Return the proper image name
*/}}
{{- define "kubeestatehub.image" -}}
{{- $registryName := .imageRoot.registry -}}
{{- $repositoryName := .imageRoot.repository -}}
{{- $tag := .imageRoot.tag | toString -}}
{{- if .global }}
    {{- if .global.imageRegistry }}
        {{- $registryName = .global.imageRegistry -}}
    {{- end -}}
{{- end -}}
{{- if $registryName }}
    {{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
{{- else -}}
    {{- printf "%s:%s" $repositoryName $tag -}}
{{- end -}}
{{- end }}

{{/*
Return the proper storage class
*/}}
{{- define "kubeestatehub.storageClass" -}}
{{- if .Values.global.storageClass -}}
    {{- .Values.global.storageClass -}}
{{- else if .Values.persistence.storageClass -}}
    {{- .Values.persistence.storageClass -}}
{{- end -}}
{{- end }}

{{/*
Compile all warnings into a single message.
*/}}
{{- define "kubeestatehub.validateValues" -}}
{{- $messages := list -}}
{{- $messages := append $messages (include "kubeestatehub.validateValues.postgresql" .) -}}
{{- $messages := append $messages (include "kubeestatehub.validateValues.redis" .) -}}
{{- $messages := without $messages "" -}}
{{- $message := join "\n" $messages -}}
{{- if $message -}}
{{-   printf "\nVALUES VALIDATION:\n%s" $message | fail -}}
{{- end -}}
{{- end -}}

{{/*
Validate PostgreSQL configuration
*/}}
{{- define "kubeestatehub.validateValues.postgresql" -}}
{{- if and .Values.postgresql.enabled (not .Values.global.postgresql.auth.password) -}}
kubeestatehub: PostgreSQL password
    You must provide a password for PostgreSQL.
    Please set global.postgresql.auth.password
{{- end -}}
{{- end -}}

{{/*
Validate Redis configuration  
*/}}
{{- define "kubeestatehub.validateValues.redis" -}}
{{- if and .Values.redis.enabled (not .Values.redis.auth.password) -}}
kubeestatehub: Redis password
    You must provide a password for Redis when auth is enabled.
    Please set redis.auth.password
{{- end -}}
{{- end }}