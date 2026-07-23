{{- define "tenant.namespace" -}}
tenant-{{ .Values.tenant.id }}
{{- end }}

{{- define "tenant.assertTgBotDeps" -}}
{{- if and .Values.tgBot.enabled (not .Values.tenantInfoTool.enabled) }}
{{- fail "tgBot.enabled=true requires tenantInfoTool.enabled=true (tg-bot reads tenant-info-tool-db-secret)" }}
{{- end }}
{{- end }}

{{- define "tenant.echoAgentImage" -}}
{{ .Values.echoAgent.image }}
{{- end }}

{{- define "tenant.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: saas-agent
saas-agent/tenant: {{ .Values.tenant.id }}
{{- end }}
