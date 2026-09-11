<?php
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, max-age=0');

$storageDir = dirname(__DIR__, 2) . DIRECTORY_SEPARATOR . 'mop-report-storage';
$storagePath = $storageDir . DIRECTORY_SEPARATOR . 'priority-overrides.json';
$lockPath = $storageDir . DIRECTORY_SEPARATOR . 'priority-overrides.lock';

function respond(array $payload, int $status = 200)
{
    http_response_code($status);
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

if (!is_dir($storageDir) && !mkdir($storageDir, 0700, true) && !is_dir($storageDir)) {
    respond(['error' => 'Storage directory is unavailable'], 500);
}

$lock = fopen($lockPath, 'c+');
if ($lock === false || !flock($lock, LOCK_EX)) {
    respond(['error' => 'Storage lock is unavailable'], 500);
}

$payload = ['schemaVersion' => 1, 'entries' => []];
if (is_file($storagePath)) {
    $stored = json_decode((string) file_get_contents($storagePath), true);
    if (is_array($stored) && isset($stored['entries']) && is_array($stored['entries'])) {
        $payload = ['schemaVersion' => 1, 'entries' => $stored['entries']];
    }
}

if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    flock($lock, LOCK_UN);
    fclose($lock);
    respond($payload);
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Allow: GET, POST');
    respond(['error' => 'Method not allowed'], 405);
}

$request = json_decode((string) file_get_contents('php://input'), true);
$snapshotDate = is_array($request) ? (string) ($request['date'] ?? '') : '';
$dealId = is_array($request) ? (string) ($request['dealId'] ?? '') : '';
$excluded = is_array($request) ? ($request['excluded'] ?? null) : null;

$validDate = preg_match('/^\d{4}-\d{2}-\d{2}$/', $snapshotDate) === 1;
$validDealId = preg_match('/^\d{1,12}$/', $dealId) === 1;
if (!$validDate || !$validDealId || !is_bool($excluded)) {
    respond(['error' => 'Invalid payload'], 422);
}

$dateEntries = isset($payload['entries'][$snapshotDate]) && is_array($payload['entries'][$snapshotDate])
    ? $payload['entries'][$snapshotDate]
    : [];
if ($excluded) {
    $dateEntries[$dealId] = true;
} else {
    unset($dateEntries[$dealId]);
}
if ($dateEntries === []) {
    unset($payload['entries'][$snapshotDate]);
} else {
    $payload['entries'][$snapshotDate] = $dateEntries;
}

$encoded = json_encode(
    $payload,
    JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES
);
if ($encoded === false || file_put_contents($storagePath, $encoded . PHP_EOL) === false) {
    respond(['error' => 'Storage write failed'], 500);
}

flock($lock, LOCK_UN);
fclose($lock);
respond($payload);
