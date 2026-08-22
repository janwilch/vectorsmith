{{- define "vectorsmith.fullname" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "vectorsmith.labels" -}}
app.kubernetes.io/name: {{ include "vectorsmith.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end -}}

{{- define "vectorsmith.selectorLabels" -}}
app.kubernetes.io/name: {{ include "vectorsmith.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
