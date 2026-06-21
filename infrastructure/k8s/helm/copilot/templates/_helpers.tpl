{{/*
Expand the name of the chart.
*/}}
{{- define "copilot.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "copilot.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "copilot.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "copilot.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "copilot.selectorLabels" -}}
app.kubernetes.io/name: {{ include "copilot.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "copilot.backendImage" -}}
{{ .Values.backend.image.repository }}:{{ .Values.backend.image.tag }}
{{- end }}

{{- define "copilot.frontendImage" -}}
{{ .Values.frontend.image.repository }}:{{ .Values.frontend.image.tag }}
{{- end }}

{{/*
Blue-Green slot label — used to switch active traffic slot
*/}}
{{- define "copilot.activeSlot" -}}
{{ .Values.blueGreen.activeSlot | default "blue" }}
{{- end }}
