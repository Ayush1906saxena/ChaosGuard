{{/*
Expand the name of the chart.
*/}}
{{- define "chaosguard.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "chaosguard.fullname" -}}
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
{{- define "chaosguard.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "chaosguard.labels" -}}
helm.sh/chart: {{ include "chaosguard.chart" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: chaosguard
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}

{{/*
Component labels - pass a dict with Root (.) and Component (string)
*/}}
{{- define "chaosguard.componentLabels" -}}
{{ include "chaosguard.labels" .Root }}
app.kubernetes.io/name: {{ .Component }}
app.kubernetes.io/instance: {{ .Root.Release.Name }}
app.kubernetes.io/component: {{ .Component }}
{{- end }}

{{/*
Selector labels for a component
*/}}
{{- define "chaosguard.selectorLabels" -}}
app.kubernetes.io/name: {{ .Component }}
app.kubernetes.io/instance: {{ .Root.Release.Name }}
app.kubernetes.io/component: {{ .Component }}
{{- end }}

{{/*
Namespace
*/}}
{{- define "chaosguard.namespace" -}}
{{- default "chaosguard" .Values.global.namespace }}
{{- end }}
