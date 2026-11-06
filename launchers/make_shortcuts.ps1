# Creates the four desktop icons (shortcuts to the .bat launchers, each with its logo). Safe to run again.
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Desktop = [Environment]::GetFolderPath('Desktop')
$sh = New-Object -ComObject WScript.Shell
$items = @(
    @{ Name = 'Mitra';               Icon = 'mitra';        Tip = 'Mitra voice agent (Sakala / iPGRS) - starts the server and opens the app' },
    @{ Name = 'Sakala WhatsApp POC'; Icon = 'whatsapp_poc'; Tip = 'Sakala AI POC on WhatsApp - starts the server and opens the app' },
    @{ Name = 'KPCL POC';            Icon = 'kpcl';         Tip = 'KPCL Generation Management assistant - starts the server and opens the app' },
    @{ Name = 'RDPR POC';            Icon = 'rdpr';         Tip = 'RDPR assistant - starts the server and opens the app' }
)
foreach ($i in $items) {
    $lnk = $sh.CreateShortcut((Join-Path $Desktop "$($i.Name).lnk"))
    $lnk.TargetPath = Join-Path $Here "$($i.Name).bat"
    $lnk.WorkingDirectory = $Here
    $lnk.IconLocation = (Join-Path $Here "icons\$($i.Icon).ico") + ',0'
    $lnk.Description = $i.Tip
    $lnk.WindowStyle = 7          # minimized: no console window pops up
    $lnk.Save()
    Write-Output "created $Desktop\$($i.Name).lnk"
}
