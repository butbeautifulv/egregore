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
{{- printf "%s:%s" .Values.image.repository .Values.image.tag }}
{{- end }}

{{- define "egregore.uiImage" -}}
{{- printf "%s:%s" .Values.ui.image.repository .Values.ui.image.tag }}
{{- end }}
