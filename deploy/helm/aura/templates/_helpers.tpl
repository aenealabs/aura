{{/*
Project Aura Helm Chart - Template Helpers
See ADR-049: Self-Hosted Deployment Strategy
*/}}

{{/*
Expand the name of the chart.
*/}}
{{- define "aura.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
*/}}
{{- define "aura.fullname" -}}
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
{{- define "aura.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "aura.labels" -}}
helm.sh/chart: {{ include "aura.chart" . }}
{{ include "aura.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: aura
{{- with .Values.global.labels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "aura.selectorLabels" -}}
app.kubernetes.io/name: {{ include "aura.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Component labels - use with named component
Usage: {{ include "aura.componentLabels" (dict "component" "api" "context" .) }}
*/}}
{{- define "aura.componentLabels" -}}
{{ include "aura.labels" .context }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Component selector labels
Usage: {{ include "aura.componentSelectorLabels" (dict "component" "api" "context" .) }}
*/}}
{{- define "aura.componentSelectorLabels" -}}
{{ include "aura.selectorLabels" .context }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "aura.serviceAccountName" -}}
{{- if .Values.rbac.serviceAccount.create }}
{{- default (include "aura.fullname" .) .Values.rbac.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.rbac.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Get image registry
*/}}
{{- define "aura.imageRegistry" -}}
{{- .Values.global.imageRegistry | default "docker.io/aenealabs" }}
{{- end }}

{{/*
Get image pull policy
*/}}
{{- define "aura.imagePullPolicy" -}}
{{- .Values.global.imagePullPolicy | default "IfNotPresent" }}
{{- end }}

{{/*
Get image for a component
Usage: {{ include "aura.image" (dict "component" .Values.api "context" .) }}
*/}}
{{- define "aura.image" -}}
{{- $registry := include "aura.imageRegistry" .context }}
{{- $repository := .component.image.repository }}
{{- $tag := .component.image.tag | default .context.Chart.AppVersion }}
{{- printf "%s/%s:%s" $registry $repository $tag }}
{{- end }}

{{/*
Image pull secrets
*/}}
{{- define "aura.imagePullSecrets" -}}
{{- if .Values.global.imagePullSecrets }}
imagePullSecrets:
{{- range .Values.global.imagePullSecrets }}
  - name: {{ . }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Return true if self-hosted deployment mode
*/}}
{{- define "aura.isSelfHosted" -}}
{{- if or (eq .Values.global.deploymentMode "self_hosted") (eq .Values.global.deploymentMode "air_gapped") }}
{{- true }}
{{- end }}
{{- end }}

{{/*
Return true if air-gapped deployment mode
*/}}
{{- define "aura.isAirGapped" -}}
{{- if eq .Values.global.deploymentMode "air_gapped" }}
{{- true }}
{{- end }}
{{- end }}

{{/*
Return true if TLS is enabled
*/}}
{{- define "aura.tlsEnabled" -}}
{{- if .Values.global.tls.enabled }}
{{- true }}
{{- end }}
{{- end }}

{{/*
Get the TLS secret name for a component
Usage: {{ include "aura.tlsSecretName" (dict "component" "api" "context" .) }}
*/}}
{{- define "aura.tlsSecretName" -}}
{{- if .context.Values.global.tls.existingSecret }}
{{- .context.Values.global.tls.existingSecret }}
{{- else }}
{{- printf "%s-%s-tls" (include "aura.fullname" .context) .component }}
{{- end }}
{{- end }}

{{/*
Return the edition (community, enterprise, enterprise_plus)
*/}}
{{- define "aura.edition" -}}
{{- .Values.global.edition | default "community" }}
{{- end }}

{{/*
Check if feature is available for current edition
Usage: {{ include "aura.featureEnabled" (dict "feature" "advanced-analytics" "context" .) }}
*/}}
{{- define "aura.featureEnabled" -}}
{{- $edition := include "aura.edition" .context }}
{{- $communityFeatures := list "basic-graphrag" "code-search" "basic-security" }}
{{- $enterpriseFeatures := list "advanced-graphrag" "sso" "rbac" "audit-logging" "advanced-security" }}
{{- $enterprisePlusFeatures := list "multi-tenancy" "custom-agents" "priority-support" "sla" }}

{{- if has .feature $communityFeatures }}
{{- true }}
{{- else if and (or (eq $edition "enterprise") (eq $edition "enterprise_plus")) (has .feature $enterpriseFeatures) }}
{{- true }}
{{- else if and (eq $edition "enterprise_plus") (has .feature $enterprisePlusFeatures) }}
{{- true }}
{{- end }}
{{- end }}

{{/*
Get database provider for a type
Usage: {{ include "aura.databaseProvider" (dict "type" "graph" "context" .) }}
*/}}
{{- define "aura.databaseProvider" -}}
{{- if eq .type "graph" }}
{{- .context.Values.databases.graph.provider | default "neo4j" }}
{{- else if eq .type "vector" }}
{{- .context.Values.databases.vector.provider | default "opensearch" }}
{{- else if eq .type "document" }}
{{- .context.Values.databases.document.provider | default "postgres" }}
{{- end }}
{{- end }}

{{/*
Get LLM provider
*/}}
{{- define "aura.llmProvider" -}}
{{- .Values.llm.provider | default "bedrock" }}
{{- end }}

{{/*
Return true if using local LLM (vLLM, TGI, Ollama)
*/}}
{{- define "aura.isLocalLLM" -}}
{{- $provider := include "aura.llmProvider" . }}
{{- if or (eq $provider "vllm") (eq $provider "tgi") (eq $provider "ollama") }}
{{- true }}
{{- end }}
{{- end }}

{{/*
Common environment variables for all services
*/}}
{{- define "aura.commonEnv" -}}
- name: AURA_DEPLOYMENT_MODE
  value: {{ .Values.global.deploymentMode | quote }}
- name: AURA_EDITION
  value: {{ include "aura.edition" . | quote }}
- name: AURA_TLS_ENABLED
  value: {{ .Values.global.tls.enabled | quote }}
- name: LOG_LEVEL
  value: {{ .Values.logging.level | default "info" | quote }}
- name: LOG_JSON
  value: {{ .Values.logging.json | default true | quote }}
{{- if .Values.tracing.enabled }}
- name: OTEL_EXPORTER_OTLP_ENDPOINT
  value: {{ .Values.tracing.otlpEndpoint | quote }}
- name: OTEL_TRACE_SAMPLER_ARG
  value: {{ .Values.tracing.sampleRate | quote }}
{{- end }}
{{- end }}

{{/*
Database connection environment variables
*/}}
{{- define "aura.databaseEnv" -}}
{{/* Graph Database */}}
{{- $graphProvider := include "aura.databaseProvider" (dict "type" "graph" "context" .) }}
- name: GRAPH_PROVIDER
  value: {{ $graphProvider | quote }}
{{- if eq $graphProvider "neo4j" }}
- name: NEO4J_URI
  value: {{ printf "bolt://%s-neo4j:7687" (include "aura.fullname" .) | quote }}
- name: NEO4J_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Values.databases.graph.neo4j.existingPasswordSecret | default (printf "%s-neo4j" (include "aura.fullname" .)) }}
      key: {{ .Values.databases.graph.neo4j.existingPasswordSecretKey | default "neo4j-password" }}
{{- end }}

{{/* Vector Database */}}
{{- $vectorProvider := include "aura.databaseProvider" (dict "type" "vector" "context" .) }}
- name: VECTOR_PROVIDER
  value: {{ $vectorProvider | quote }}
{{- if eq $vectorProvider "opensearch" }}
- name: OPENSEARCH_HOST
  value: {{ printf "%s-opensearch" (include "aura.fullname" .) | quote }}
- name: OPENSEARCH_PORT
  value: "9200"
- name: OPENSEARCH_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Values.databases.vector.opensearch.existingPasswordSecret | default (printf "%s-opensearch" (include "aura.fullname" .)) }}
      key: admin-password
{{- end }}

{{/* Document Database */}}
{{- $docProvider := include "aura.databaseProvider" (dict "type" "document" "context" .) }}
- name: DOCUMENT_PROVIDER
  value: {{ $docProvider | quote }}
{{- if eq $docProvider "postgres" }}
- name: POSTGRES_HOST
  value: {{ printf "%s-postgres" (include "aura.fullname" .) | quote }}
- name: POSTGRES_PORT
  value: "5432"
- name: POSTGRES_DATABASE
  value: {{ .Values.databases.document.postgres.database | quote }}
- name: POSTGRES_USERNAME
  value: {{ .Values.databases.document.postgres.username | quote }}
- name: POSTGRES_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Values.databases.document.postgres.existingPasswordSecret | default (printf "%s-postgres" (include "aura.fullname" .)) }}
      key: postgres-password
{{- end }}
{{- end }}

{{/*
LLM connection environment variables
*/}}
{{- define "aura.llmEnv" -}}
{{- $provider := include "aura.llmProvider" . }}
- name: LLM_PROVIDER
  value: {{ $provider | quote }}
{{- if eq $provider "bedrock" }}
- name: AWS_REGION
  value: {{ .Values.llm.bedrock.region | quote }}
{{- else if eq $provider "vllm" }}
- name: VLLM_API_BASE
  value: {{ printf "http://%s-vllm:8000/v1" (include "aura.fullname" .) | quote }}
- name: VLLM_MODEL
  value: {{ .Values.llm.vllm.model | quote }}
{{- else if eq $provider "tgi" }}
- name: TGI_API_BASE
  value: {{ printf "http://%s-tgi:8080" (include "aura.fullname" .) | quote }}
- name: TGI_MODEL
  value: {{ .Values.llm.tgi.model | quote }}
{{- else if eq $provider "ollama" }}
- name: OLLAMA_HOST
  value: {{ printf "http://%s-ollama:11434" (include "aura.fullname" .) | quote }}
{{- end }}
{{- end }}

{{/*
Redis connection environment variables
*/}}
{{- define "aura.redisEnv" -}}
{{- if .Values.redis.enabled }}
- name: REDIS_HOST
  value: {{ printf "%s-redis-master" (include "aura.fullname" .) | quote }}
- name: REDIS_PORT
  value: "6379"
{{- if .Values.redis.auth.enabled }}
- name: REDIS_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Values.redis.auth.existingSecret | default (printf "%s-redis" (include "aura.fullname" .)) }}
      key: redis-password
{{- end }}
{{- end }}
{{- end }}

{{/*
Storage (MinIO) connection environment variables
*/}}
{{- define "aura.storageEnv" -}}
{{- if .Values.storage.minio.enabled }}
- name: MINIO_ENDPOINT
  value: {{ printf "%s-minio:9000" (include "aura.fullname" .) | quote }}
- name: MINIO_ACCESS_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.storage.minio.existingSecret | default (printf "%s-minio" (include "aura.fullname" .)) }}
      key: root-user
- name: MINIO_SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.storage.minio.existingSecret | default (printf "%s-minio" (include "aura.fullname" .)) }}
      key: root-password
{{- end }}
{{- end }}

{{/*
Pod security context (restricted PSS compliant)
*/}}
{{- define "aura.podSecurityContext" -}}
runAsNonRoot: true
seccompProfile:
  type: RuntimeDefault
{{- end }}

{{/*
Container security context (restricted PSS compliant)
*/}}
{{- define "aura.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
runAsNonRoot: true
capabilities:
  drop:
    - ALL
{{- end }}

{{/*
Liveness probe for a component
Usage: {{ include "aura.livenessProbe" .Values.api.healthChecks.liveness | nindent 10 }}
*/}}
{{- define "aura.livenessProbe" -}}
livenessProbe:
  httpGet:
    path: {{ .path }}
    port: {{ .port }}
    scheme: {{ .scheme | default "HTTPS" }}
  initialDelaySeconds: {{ .initialDelaySeconds | default 30 }}
  periodSeconds: {{ .periodSeconds | default 10 }}
  timeoutSeconds: {{ .timeoutSeconds | default 5 }}
  failureThreshold: {{ .failureThreshold | default 3 }}
{{- end }}

{{/*
Readiness probe for a component
Usage: {{ include "aura.readinessProbe" .Values.api.healthChecks.readiness | nindent 10 }}
*/}}
{{- define "aura.readinessProbe" -}}
readinessProbe:
  httpGet:
    path: {{ .path }}
    port: {{ .port }}
    scheme: {{ .scheme | default "HTTPS" }}
  initialDelaySeconds: {{ .initialDelaySeconds | default 10 }}
  periodSeconds: {{ .periodSeconds | default 5 }}
  timeoutSeconds: {{ .timeoutSeconds | default 3 }}
  failureThreshold: {{ .failureThreshold | default 3 }}
{{- end }}

{{/*
Standard annotations for all resources
*/}}
{{- define "aura.annotations" -}}
{{- with .Values.global.annotations }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Checksum annotation for config changes triggering pod restart
Usage: {{ include "aura.configChecksum" . }}
*/}}
{{- define "aura.configChecksum" -}}
checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
{{- end }}
