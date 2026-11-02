param([Parameter(Mandatory=$true)][string]$InputDocx,[Parameter(Mandatory=$true)][string]$PdfPath)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$docPath = [System.IO.Path]::GetFullPath($InputDocx)
$pdfOutput = [System.IO.Path]::GetFullPath($PdfPath)
if (-not [System.IO.File]::Exists($docPath)) { throw "Input DOCX does not exist" }
[System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($pdfOutput)) | Out-Null
$word = $null
$document = $null
$priorUpdateLinks = $null
try {
  $word = New-Object -ComObject Word.Application
  $word.Visible = $false
  $word.DisplayAlerts = 0
  $word.AutomationSecurity = 3
  $priorUpdateLinks = $word.Options.UpdateLinksAtOpen
  $word.Options.UpdateLinksAtOpen = $false
  $document = $word.Documents.Open($docPath,$false,$false,$false)
  $document.Fields.Update() | Out-Null
  foreach ($toc in $document.TablesOfContents) { $toc.Update() }
  $document.Repaginate()
  foreach ($toc in $document.TablesOfContents) { $toc.UpdatePageNumbers() }
  $document.Fields.Update() | Out-Null
  $document.Repaginate()
  $pages = $document.ComputeStatistics(2)
  $document.Save()
  $document.ExportAsFixedFormat($pdfOutput,17)
  [pscustomobject]@{engine='Microsoft Word COM';pages=$pages;pdf=$pdfOutput;docx=$docPath;tocCount=$document.TablesOfContents.Count} | ConvertTo-Json -Compress
} finally {
  if ($null -ne $document) {
    $document.Close(0)
    [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($document) | Out-Null
  }
  if ($null -ne $word) {
    if ($null -ne $priorUpdateLinks) { $word.Options.UpdateLinksAtOpen = $priorUpdateLinks }
    $word.Quit(0)
    [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) | Out-Null
  }
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
}
