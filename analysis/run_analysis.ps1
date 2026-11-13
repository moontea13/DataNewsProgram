param(
    [string]$Python = 'python',
    [ValidateSet('base','style','all','check')][string]$Stage = 'base',
    [string]$Source = '',
    [string]$Output = '',
    [string]$StyleOutput = '',
    [switch]$SkipInference,
    [switch]$SkipDownload
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pipelineArgs = @((Join-Path $projectRoot 'run_pipeline.py'), $Stage)
if ($Source) { $pipelineArgs += @('--source', $Source) }
if ($Output) { $pipelineArgs += @('--output', $Output) }
if ($StyleOutput) { $pipelineArgs += @('--style-output', $StyleOutput) }
if ($SkipInference) { $pipelineArgs += '--skip-inference' }
if ($SkipDownload) { $pipelineArgs += '--skip-download' }
& $Python -X utf8 @pipelineArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
