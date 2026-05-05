{{/*
Expand the chart name.
*/}}
{{- define "ml-serving-platform.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "ml-serving-platform.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Chart label.
*/}}
{{- define "ml-serving-platform.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common labels.
*/}}
{{- define "ml-serving-platform.labels" -}}
helm.sh/chart: {{ include "ml-serving-platform.chart" . }}
{{ include "ml-serving-platform.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Selector labels.
*/}}
{{- define "ml-serving-platform.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ml-serving-platform.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Render a component image with optional global registry and tag fallback.
Usage: include "ml-serving-platform.image" (list . .Values.component.image)
*/}}
{{- define "ml-serving-platform.image" -}}
{{- $root := index . 0 -}}
{{- $image := index . 1 -}}
{{- if $root.Values.global.imageRegistry }}{{ $root.Values.global.imageRegistry }}/{{ end }}{{ $image.repository }}:{{ default $root.Values.global.imageTag $image.tag }}
{{- end -}}
