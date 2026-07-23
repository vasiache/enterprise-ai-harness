{{- define "shared-tools.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "shared-tools.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: saas-agent
{{- end }}
