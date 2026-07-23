{{- define "egregore.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "egregore.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s" (include "egregore.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "egregore.labels" -}}
app.kubernetes.io/name: {{ include "egregore.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "egregore.image" -}}
{{- printf "%s:%s" .Values.api.image.repository .Values.api.image.tag }}
{{- end }}

{{- define "egregore.apiImage" -}}
{{- printf "%s:%s" .Values.api.image.repository .Values.api.image.tag }}
{{- end }}

{{- define "egregore.dispatcherImage" -}}
{{- printf "%s:%s" .Values.dispatcher.image.repository .Values.dispatcher.image.tag }}
{{- end }}

{{- define "egregore.agentRuntimeImage" -}}
{{- printf "%s:%s" .Values.agentRuntime.image.repository .Values.agentRuntime.image.tag }}
{{- end }}

{{- define "egregore.uiImage" -}}
{{- printf "%s:%s" .Values.ui.image.repository .Values.ui.image.tag }}
{{- end }}

{{- define "egregore.toolGatewayImage" -}}
{{- printf "%s:%s" .Values.toolGateway.image.repository .Values.toolGateway.image.tag }}
{{- end }}

{{- define "egregore.modelGatewayImage" -}}
{{- printf "%s:%s" .Values.modelGateway.image.repository .Values.modelGateway.image.tag }}
{{- end }}

{{- define "egregore.podSecurityContext" -}}
automountServiceAccountToken: false
securityContext:
  runAsNonRoot: true
  runAsUser: 10000
  runAsGroup: 10000
  fsGroup: 10000
  seccompProfile:
    type: RuntimeDefault
{{- end }}

{{- define "egregore.containerSecurityContext" -}}
securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop:
      - ALL
{{- end }}
