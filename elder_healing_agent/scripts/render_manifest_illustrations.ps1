$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing

$baseDir = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$manifestPath = Join-Path $baseDir "data\illustration_manifest.json"

if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "Manifest not found: $manifestPath"
}

$manifest = Get-Content -Encoding UTF8 -LiteralPath $manifestPath | ConvertFrom-Json
$size = 1080

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

function PathRect([float]$x, [float]$y, [float]$w, [float]$h, [float]$r) {
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $d = $r * 2
    $path.AddArc($x, $y, $d, $d, 180, 90)
    $path.AddArc($x + $w - $d, $y, $d, $d, 270, 90)
    $path.AddArc($x + $w - $d, $y + $h - $d, $d, $d, 0, 90)
    $path.AddArc($x, $y + $h - $d, $d, $d, 90, 90)
    $path.CloseFigure()
    return $path
}

function FillRoundRect($g, [float]$x, [float]$y, [float]$w, [float]$h, [float]$r, $brush, $pen = $null) {
    $path = PathRect $x $y $w $h $r
    $g.FillPath($brush, $path)
    if ($pen) { $g.DrawPath($pen, $path) }
    $path.Dispose()
}

function DrawPaper($g, [int]$seed) {
    $rect = New-Object System.Drawing.Rectangle 0, 0, $size, $size
    $bg = New-Object System.Drawing.Drawing2D.LinearGradientBrush `
        $rect, (Color "FBF7EF"), (Color "EFE9DC"), 35
    $g.FillRectangle($bg, $rect)
    $bg.Dispose()

    $rand = New-Object System.Random $seed
    for ($i = 0; $i -lt 900; $i++) {
        $x = $rand.Next(0, $size)
        $y = $rand.Next(0, $size)
        $len = $rand.Next(8, 34)
        $alpha = $rand.Next(10, 32)
        $shade = if (($i % 2) -eq 0) { "D4CBBB" } else { "FFFFFF" }
        $g.DrawLine((Pen $shade 1 $alpha), $x, $y, [Math]::Min($size, $x + $len), $y + $rand.Next(-2, 3))
    }

    $g.DrawRectangle((Pen "D8CBB7" 3 80), 52, 52, $size - 104, $size - 104)
}

function DrawShadow($g, [float]$x, [float]$y, [float]$w, [float]$h) {
    $g.FillEllipse((Brush "6F6254" 34), $x, $y, $w, $h)
}

function DrawCrane($g, [float]$x, [float]$y, [float]$s) {
    DrawShadow $g ($x - 55 * $s) ($y + 128 * $s) (210 * $s) (38 * $s)
    $body = New-Object System.Drawing.Drawing2D.GraphicsPath
    $body.AddEllipse($x, $y + 55 * $s, 165 * $s, 105 * $s)
    $g.FillPath((Brush "FFFDF5" 245), $body)
    $g.DrawPath((Pen "D7B55E" (5 * $s) 220), $body)
    $body.Dispose()

    $wing = New-Object System.Drawing.Drawing2D.GraphicsPath
    $wing.AddBezier($x + 35 * $s, $y + 85 * $s, $x + 95 * $s, $y + 45 * $s, $x + 150 * $s, $y + 88 * $s, $x + 122 * $s, $y + 135 * $s)
    $wing.AddBezier($x + 122 * $s, $y + 135 * $s, $x + 80 * $s, $y + 152 * $s, $x + 40 * $s, $y + 124 * $s, $x + 35 * $s, $y + 85 * $s)
    $wing.CloseFigure()
    $g.FillPath((Brush "E5C16F" 210), $wing)
    $g.DrawPath((Pen "BE923E" (3 * $s) 170), $wing)
    $wing.Dispose()

    $neck = New-Object System.Drawing.Drawing2D.GraphicsPath
    $neck.AddBezier($x + 137 * $s, $y + 86 * $s, $x + 180 * $s, $y + 8 * $s, $x + 133 * $s, $y - 32 * $s, $x + 97 * $s, $y + 3 * $s)
    $g.DrawPath((Pen "D7B55E" (22 * $s) 210), $neck)
    $g.DrawPath((Pen "FFFDF5" (15 * $s) 245), $neck)
    $neck.Dispose()

    $g.FillEllipse((Brush "FFFDF5" 245), $x + 76 * $s, $y - 16 * $s, 66 * $s, 52 * $s)
    $g.DrawEllipse((Pen "D7B55E" (3 * $s) 210), $x + 76 * $s, $y - 16 * $s, 66 * $s, 52 * $s)
    $beak = New-Object System.Drawing.Drawing2D.GraphicsPath
    $beak.AddPolygon([System.Drawing.PointF[]]@(
        (New-Object System.Drawing.PointF ($x + 84 * $s), ($y + 4 * $s)),
        (New-Object System.Drawing.PointF ($x + 30 * $s), ($y - 2 * $s)),
        (New-Object System.Drawing.PointF ($x + 83 * $s), ($y + 21 * $s))
    ))
    $g.FillPath((Brush "C99632" 235), $beak)
    $beak.Dispose()
    $g.FillEllipse((Brush "4F3B1B" 230), $x + 106 * $s, $y + 2 * $s, 8 * $s, 8 * $s)
}

function DrawPhone($g, [float]$x, [float]$y, [float]$w, [float]$h, [bool]$glow = $true) {
    if ($glow) { $g.FillEllipse((Brush "F3D977" 48), $x - 35, $y - 35, $w + 70, $h + 70) }
    FillRoundRect $g $x $y $w $h 28 (Brush "3E4348" 245) (Pen "272C30" 4 180)
    FillRoundRect $g ($x + 15) ($y + 20) ($w - 30) ($h - 48) 18 (Brush "D8F1ED" 220) $null
    $g.FillEllipse((Brush "B7C1BF" 180), ($x + $w / 2 - 10), ($y + $h - 22), 20, 8)
}

function DrawBowl($g, [float]$x, [float]$y, [float]$s) {
    $g.FillEllipse((Brush "F4EFE4" 245), $x, $y, 180 * $s, 68 * $s)
    $g.DrawEllipse((Pen "B9A384" (4 * $s) 180), $x, $y, 180 * $s, 68 * $s)
    $g.FillPie((Brush "D8EFE7" 230), $x + 12 * $s, $y + 22 * $s, 156 * $s, 92 * $s, 0, 180)
    $g.DrawArc((Pen "8DB9AE" (4 * $s) 180), $x + 12 * $s, $y + 22 * $s, 156 * $s, 92 * $s, 0, 180)
    $g.FillEllipse((Brush "FFF7D6" 210), $x + 36 * $s, $y + 10 * $s, 108 * $s, 35 * $s)
}

function DrawMedicine($g, [float]$x, [float]$y, [float]$s) {
    FillRoundRect $g $x $y (120 * $s) (76 * $s) (12 * $s) (Brush "F8F6ED" 245) (Pen "A8AAA8" (3 * $s) 150)
    $g.FillRectangle((Brush "F08A54" 210), $x + 12 * $s, $y + 16 * $s, 96 * $s, 16 * $s)
    $g.DrawLine((Pen "7CA9B6" (3 * $s) 170), $x + 22 * $s, $y + 50 * $s, $x + 98 * $s, $y + 50 * $s)
}

function DrawWater($g, [float]$x, [float]$y, [float]$s) {
    FillRoundRect $g $x $y (64 * $s) (120 * $s) (22 * $s) (Brush "FDFDF9" 155) (Pen "9DC7CF" (3 * $s) 160)
    $g.FillRectangle((Brush "95D2E3" 125), $x + 9 * $s, $y + 54 * $s, 46 * $s, 44 * $s)
}

function DrawLamp($g, [float]$x, [float]$y, [float]$s) {
    $g.DrawLine((Pen "6F6A5E" (5 * $s) 160), $x + 45 * $s, $y + 82 * $s, $x + 45 * $s, $y + 170 * $s)
    $shade = New-Object System.Drawing.Drawing2D.GraphicsPath
    $shade.AddPolygon([System.Drawing.PointF[]]@(
        (New-Object System.Drawing.PointF ($x), ($y + 88 * $s)),
        (New-Object System.Drawing.PointF ($x + 90 * $s), ($y + 88 * $s)),
        (New-Object System.Drawing.PointF ($x + 70 * $s), ($y + 22 * $s)),
        (New-Object System.Drawing.PointF ($x + 20 * $s), ($y + 22 * $s))
    ))
    $g.FillPath((Brush "EECF82" 210), $shade)
    $g.DrawPath((Pen "B99443" (3 * $s) 140), $shade)
    $shade.Dispose()
    $g.FillEllipse((Brush "EECF82" 200), $x + 12 * $s, $y + 164 * $s, 70 * $s, 16 * $s)
    $g.FillEllipse((Brush "F5D987" 45), $x - 55 * $s, $y - 12 * $s, 200 * $s, 160 * $s)
}

function DrawBed($g, [float]$x, [float]$y, [float]$s) {
    FillRoundRect $g $x $y (390 * $s) (190 * $s) (32 * $s) (Brush "E8E0D2" 230) (Pen "9C9080" (4 * $s) 150)
    FillRoundRect $g ($x + 38 * $s) ($y + 28 * $s) (124 * $s) (78 * $s) (22 * $s) (Brush "FFFDF5" 240) (Pen "D9D1C5" (2 * $s) 150)
    FillRoundRect $g ($x + 118 * $s) ($y + 48 * $s) (235 * $s) (110 * $s) (36 * $s) (Brush "F9F8F1" 245) (Pen "D7D4CA" (3 * $s) 130)
    $g.DrawLine((Pen "7C827E" (5 * $s) 140), $x + 24 * $s, $y + 190 * $s, $x + 24 * $s, $y + 230 * $s)
    $g.DrawLine((Pen "7C827E" (5 * $s) 140), $x + 356 * $s, $y + 190 * $s, $x + 356 * $s, $y + 230 * $s)
}

function DrawCard($g, [float]$x, [float]$y, [float]$s) {
    FillRoundRect $g $x $y (200 * $s) (120 * $s) (16 * $s) (Brush "A8D8C2" 230) (Pen "6EA48E" (4 * $s) 170)
    $g.DrawLine((Pen "FDF9EF" (8 * $s) 150), $x + 18 * $s, $y + 35 * $s, $x + 182 * $s, $y + 35 * $s)
    $g.DrawEllipse((Pen "FDF9EF" (5 * $s) 125), $x + 32 * $s, $y + 58 * $s, 52 * $s, 34 * $s)
}

function DrawScene($g, [string]$key, [int]$seed) {
    DrawPaper $g $seed
    DrawShadow $g 170 758 740 95

    switch ($key) {
        "bedside-medicine-water" {
            DrawBed $g 210 390 1.18
            DrawLamp $g 760 330 1.12
            DrawMedicine $g 235 695 1.18
            DrawWater $g 390 650 1.15
            DrawCrane $g 520 360 1.0
        }
        "phone-rice-bowl-tired" {
            FillRoundRect $g 170 605 740 145 28 (Brush "E8DDC8" 210) (Pen "BBAE94" 4 130)
            DrawPhone $g 630 410 145 250 $true
            DrawBowl $g 270 485 1.35
            DrawMedicine $g 505 617 1.1
            DrawCrane $g 432 345 0.92
        }
        "lights-off-warm-water" {
            DrawBed $g 220 445 1.15
            DrawWater $g 730 590 1.25
            $g.FillEllipse((Brush "F3D27D" 115), 725, 210, 130, 130)
            DrawLamp $g 140 370 0.85
            DrawCrane $g 475 410 0.9
        }
        "short-phone-call-kitchen" {
            FillRoundRect $g 160 610 760 160 26 (Brush "E9DEC9" 220) (Pen "BDAF92" 4 130)
            DrawLamp $g 495 210 1.1
            DrawPhone $g 575 450 130 226 $false
            DrawBowl $g 310 518 1.25
            DrawCrane $g 405 398 0.88
        }
        "bank-card-medicine-bowl" {
            FillRoundRect $g 150 600 780 165 30 (Brush "EADFCB" 220) (Pen "BDAF92" 4 130)
            DrawCard $g 250 462 1.15
            DrawMedicine $g 505 510 1.2
            DrawBowl $g 640 480 1.1
            DrawCrane $g 410 340 0.82
        }
        "phone-on-table-warm-dinner" {
            FillRoundRect $g 150 600 780 165 30 (Brush "EADFCB" 220) (Pen "BDAF92" 4 130)
            DrawPhone $g 250 435 128 220 $false
            DrawBowl $g 505 480 1.45
            DrawCrane $g 465 328 0.82
            $steam = Pen "B7CFC7" 4 80
            $g.DrawBezier($steam, 565, 466, 540, 425, 590, 408, 570, 365)
            $g.DrawBezier($steam, 640, 462, 615, 422, 662, 403, 645, 364)
        }
        default {
            DrawCrane $g 430 360 1.0
            DrawBowl $g 420 570 1.15
            DrawWater $g 640 520 1.0
        }
    }

    $g.DrawRectangle((Pen "FFFFFF" 7 65), 68, 68, $size - 136, $size - 136)
}

foreach ($item in $manifest.assignments) {
    $target = [string]$item.target
    if (-not $target) { continue }
    $targetDir = Split-Path -Parent $target
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

    $bitmap = New-Object System.Drawing.Bitmap $size, $size
    $g = [System.Drawing.Graphics]::FromImage($bitmap)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit

    try {
        $seed = 3000 + [Math]::Abs(([string]$item.scene_key).GetHashCode() % 100000)
        DrawScene $g ([string]$item.scene_key) $seed
        $bitmap.Save($target, [System.Drawing.Imaging.ImageFormat]::Png)
        Write-Output $target
    }
    finally {
        if ($g) { $g.Dispose() }
        if ($bitmap) { $bitmap.Dispose() }
    }
}
