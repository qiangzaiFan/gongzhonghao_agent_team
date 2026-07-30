$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing

$outDir = Join-Path $PSScriptRoot "."
$pngPath = Join-Path $outDir "qingchuan-huanghe-avatar-1024.png"
$smallPngPath = Join-Path $outDir "qingchuan-huanghe-avatar-512.png"

$size = 1024
$bitmap = New-Object System.Drawing.Bitmap $size, $size
$g = [System.Drawing.Graphics]::FromImage($bitmap)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit

function Color([string]$hex, [int]$alpha = 255) {
    $hex = $hex.TrimStart("#")
    $r = [Convert]::ToInt32($hex.Substring(0, 2), 16)
    $g = [Convert]::ToInt32($hex.Substring(2, 2), 16)
    $b = [Convert]::ToInt32($hex.Substring(4, 2), 16)
    return [System.Drawing.Color]::FromArgb($alpha, $r, $g, $b)
}

function Brush([string]$hex, [int]$alpha = 255) {
    return New-Object System.Drawing.SolidBrush (Color $hex $alpha)
}

function Pen([string]$hex, [float]$width, [int]$alpha = 255) {
    $pen = New-Object System.Drawing.Pen (Color $hex $alpha), $width
    $pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
    return $pen
}

try {
    $bgRect = New-Object System.Drawing.Rectangle 0, 0, $size, $size
    $bg = New-Object System.Drawing.Drawing2D.LinearGradientBrush `
        $bgRect, (Color "F8F3E8"), (Color "DCECE4"), 55
    $g.FillRectangle($bg, $bgRect)

    $outer = New-Object System.Drawing.Drawing2D.GraphicsPath
    $outer.AddEllipse(88, 88, 848, 848)
    $outerBrush = New-Object System.Drawing.Drawing2D.PathGradientBrush $outer
    $outerBrush.CenterColor = Color "F9F5EA"
    $outerBrush.SurroundColors = @((Color "CFE6DC"))
    $g.FillPath($outerBrush, $outer)
    $g.DrawPath((Pen "7DB8A7" 10 120), $outer)
    $g.SetClip($outer)

    $inner = New-Object System.Drawing.Drawing2D.GraphicsPath
    $inner.AddEllipse(145, 145, 734, 734)
    $g.DrawPath((Pen "F1D48A" 5 120), $inner)

    $sunBrush = Brush "E9B856" 230
    $g.FillEllipse($sunBrush, 690, 205, 118, 118)
    $g.FillEllipse((Brush "F5D891" 70), 656, 171, 186, 186)

    $mountain = New-Object System.Drawing.Drawing2D.GraphicsPath
    $mountain.AddBezier(205, 575, 330, 445, 420, 445, 520, 585)
    $mountain.AddBezier(520, 585, 605, 468, 710, 460, 820, 600)
    $mountain.AddLine(820, 660, 205, 660)
    $mountain.CloseFigure()
    $g.FillPath((Brush "B7D5C9" 90), $mountain)

    $g.FillEllipse((Brush "7FB7B0" 165), 116, 632, 822, 232)

    $river2 = New-Object System.Drawing.Drawing2D.GraphicsPath
    $river2.AddBezier(185, 720, 320, 684, 438, 758, 585, 718)
    $river2.AddBezier(585, 718, 690, 690, 770, 700, 845, 730)
    $g.DrawPath((Pen "EFF8F4" 18 175), $river2)

    $river3 = New-Object System.Drawing.Drawing2D.GraphicsPath
    $river3.AddBezier(250, 790, 405, 740, 535, 815, 710, 760)
    $g.DrawPath((Pen "D6EDE8" 12 145), $river3)

    $shadow = New-Object System.Drawing.Drawing2D.GraphicsPath
    $shadow.AddEllipse(332, 625, 305, 52)
    $g.FillPath((Brush "5C8D86" 42), $shadow)

    $body = New-Object System.Drawing.Drawing2D.GraphicsPath
    $body.AddEllipse(356, 430, 255, 158)
    $g.FillPath((Brush "FFFDF5" 250), $body)
    $g.DrawPath((Pen "D8B15D" 6 230), $body)

    $wing = New-Object System.Drawing.Drawing2D.GraphicsPath
    $wing.AddBezier(418, 458, 495, 410, 575, 440, 587, 504)
    $wing.AddBezier(587, 504, 548, 565, 465, 562, 408, 525)
    $wing.AddBezier(408, 525, 444, 512, 462, 486, 418, 458)
    $wing.CloseFigure()
    $g.FillPath((Brush "E3BF68" 230), $wing)
    $g.DrawPath((Pen "C6963A" 4 210), $wing)

    $wingLine = New-Object System.Drawing.Drawing2D.GraphicsPath
    $wingLine.AddBezier(448, 490, 500, 465, 536, 484, 555, 523)
    $g.DrawPath((Pen "FFF6DA" 8 130), $wingLine)

    $neckBack = New-Object System.Drawing.Drawing2D.GraphicsPath
    $neckBack.AddBezier(575, 454, 615, 372, 602, 304, 548, 277)
    $g.DrawPath((Pen "D8B15D" 52 230), $neckBack)

    $neck = New-Object System.Drawing.Drawing2D.GraphicsPath
    $neck.AddBezier(573, 452, 612, 373, 598, 311, 548, 284)
    $g.DrawPath((Pen "FFFDF5" 38 255), $neck)

    $head = New-Object System.Drawing.Drawing2D.GraphicsPath
    $head.AddEllipse(509, 251, 82, 67)
    $g.FillPath((Brush "FFFDF5" 255), $head)
    $g.DrawPath((Pen "D8B15D" 5 220), $head)

    $beak = New-Object System.Drawing.Drawing2D.GraphicsPath
    $beak.AddPolygon([System.Drawing.Point[]]@(
        (New-Object System.Drawing.Point 520, 282),
        (New-Object System.Drawing.Point 445, 264),
        (New-Object System.Drawing.Point 516, 303)
    ))
    $g.FillPath((Brush "C99430" 245), $beak)

    $eyeBrush = Brush "4F3B1B" 235
    $g.FillEllipse($eyeBrush, 544, 274, 11, 11)

    $legPen = Pen "B78937" 9 220
    $g.DrawLine($legPen, 456, 580, 438, 655)
    $g.DrawLine($legPen, 514, 580, 525, 653)
    $g.DrawLine((Pen "B78937" 6 200), 438, 655, 404, 665)
    $g.DrawLine((Pen "B78937" 6 200), 525, 653, 560, 663)

    $softArc = New-Object System.Drawing.Drawing2D.GraphicsPath
    $softArc.AddArc(210, 202, 600, 600, 205, 126)
    $g.DrawPath((Pen "FFFFFF" 20 60), $softArc)

    $g.ResetClip()
    $g.DrawPath((Pen "7DB8A7" 10 120), $outer)
    $g.DrawPath((Pen "F1D48A" 5 120), $inner)

    $bitmap.Save($pngPath, [System.Drawing.Imaging.ImageFormat]::Png)

    $small = New-Object System.Drawing.Bitmap 512, 512
    $smallGraphics = [System.Drawing.Graphics]::FromImage($small)
    $smallGraphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $smallGraphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $smallGraphics.DrawImage($bitmap, 0, 0, 512, 512)
    $small.Save($smallPngPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $smallGraphics.Dispose()
    $small.Dispose()

    Write-Output $pngPath
    Write-Output $smallPngPath
}
finally {
    if ($g) { $g.Dispose() }
    if ($bitmap) { $bitmap.Dispose() }
}
