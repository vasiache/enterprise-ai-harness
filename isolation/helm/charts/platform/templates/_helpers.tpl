{{- define "platform.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "platform.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: saas-agent-platform
{{- end }}

{{- define "platform.postgresHost" -}}
postgres.{{ .Release.Namespace }}.svc.cluster.local
{{- end }}

{{- define "platform.gotrueDbUrl" -}}
postgres://supabase_auth_admin:{{ .Values.postgres.superuserPassword }}@{{ include "platform.postgresHost" . }}:{{ .Values.postgres.port }}/{{ .Values.postgres.database }}?search_path=auth&sslmode=disable
{{- end }}

{{- define "platform.appDbUrl" -}}
postgresql://app_user:{{ .Values.postgres.appUserPassword }}@{{ include "platform.postgresHost" . }}:{{ .Values.postgres.port }}/{{ .Values.postgres.database }}
{{- end }}
