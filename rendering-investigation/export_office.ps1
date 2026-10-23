$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$out = Join-Path $root 'office-pdf'
New-Item -ItemType Directory -Force -Path $out | Out-Null
foreach ($name in 'word.pdf', 'excel.pdf', 'powerpoint.pdf') {
    $target = Join-Path $out $name
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target }
}

$word = New-Object -ComObject Word.Application
try {
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open((Join-Path $root 'layout.docx'), $false, $true)
    try { $doc.SaveAs2((Join-Path $out 'word.pdf'), 17) }
    finally { $doc.Close(0) }
} finally { $word.Quit() }

$excel = New-Object -ComObject Excel.Application
try {
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $book = $excel.Workbooks.Open((Join-Path $root 'layout.xlsx'), 0, $true)
    try { $book.ExportAsFixedFormat(0, (Join-Path $out 'excel.pdf')) }
    finally { $book.Close($false) }
} finally { $excel.Quit() }

$powerpoint = New-Object -ComObject PowerPoint.Application
try {
    $deck = $powerpoint.Presentations.Open((Join-Path $root 'layout.pptx'), $true, $false, $false)
    try { $deck.SaveAs((Join-Path $out 'powerpoint.pdf'), 32) }
    finally { $deck.Close() }
} finally { $powerpoint.Quit() }

Get-ChildItem $out -Filter '*.pdf' | Select-Object Name,Length
