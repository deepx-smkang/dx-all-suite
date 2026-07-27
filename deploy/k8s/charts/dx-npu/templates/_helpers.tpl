{{- define "dx-npu.labels" -}}
app.kubernetes.io/name: dx-npu
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
