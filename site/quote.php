<?php
/*
 * Sends a quotation request from the GROZ catalogue website (groz.tools / groz.in) by email to the
 * sales desk. The catalogue page posts the request here as JSON (site/assets/js/core.mjs quotePayload);
 * this file checks every value, builds the email itself (nothing the visitor sends is used as HTML) and
 * hands it to the server's own mail setup with PHP mail(), the same way as general.tools/inquiry.php.
 * No passwords or keys live here. Answer: {"ok":true,"mailed":true|false,"ref":"QR-…"} or an error.
 *
 * The page falls back to "prepared, not sent" (copy, print, email it yourself) whenever this file
 * cannot be reached or does not answer {"ok":true,"mailed":true}: on the Vercel copy, in local
 * previews, or if the server cannot send mail.
 */
declare(strict_types=1);

const QUOTE_TO   = 'cart@groz.tools';                       // where requests go
const QUOTE_FROM = 'GROZ Catalogue <noreply@groz.tools>';   // the sender shown in the mailbox
const SITE       = 'https://groz.tools/site/';
const ORIGINS    = ['https://groz.tools', 'https://www.groz.tools', 'https://groz.in', 'https://www.groz.in',
                    'http://127.0.0.1:8964', 'http://localhost:8964'];   // the last two: local test only
const MAX_LINES  = 300;
const MAX_QTY    = 99999;
const PER_IP     = 5;      // requests per visitor (IP address) …
const PER_IP_S   = 600;    // … in 10 minutes
const PER_HOUR   = 60;     // requests from everyone together in one hour
const CURRENCIES = ['USD' => 'US dollars (USD)', 'EUR' => 'Euros (EUR)', 'INR' => 'Indian rupees (INR)', '' => 'No preference'];

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');

function answer(int $code, array $body): void {
    http_response_code($code);
    echo json_encode($body, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

/** One line of text: no control characters, spaces squeezed, at most $max characters. */
function line($v, int $max): string {
    $s = is_scalar($v) ? (string)$v : '';
    $s = preg_replace('/[\x00-\x1F\x7F]+/u', ' ', $s) ?? '';
    $s = trim(preg_replace('/\s+/u', ' ', $s) ?? '');
    return cut($s, $max);
}

/** Several lines (the notes): line breaks kept, other control characters removed. */
function block($v, int $max): string {
    $s = is_scalar($v) ? str_replace(["\r\n", "\r"], "\n", (string)$v) : '';
    $s = preg_replace('/[\x00-\x09\x0B-\x1F\x7F]+/u', ' ', $s) ?? '';
    return cut(trim($s), $max);
}

function cut(string $s, int $max): string {
    if (function_exists('mb_substr')) return mb_substr($s, 0, $max, 'UTF-8');
    return preg_match('/^.{0,' . $max . '}/us', $s, $m) ? $m[0] : substr($s, 0, $max);
}

function h(string $s): string { return htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }

/** Allows the request if this visitor and everyone together are under their limits (best effort). */
function allowed(string $ip): bool {
    $dir = sys_get_temp_dir();
    $now = time();
    $ok = true;
    foreach ([['groz-quote-' . hash('sha256', $ip), PER_IP, PER_IP_S], ['groz-quote-all', PER_HOUR, 3600]] as [$name, $limit, $span]) {
        $file = $dir . '/' . $name . '.json';
        $fh = @fopen($file, 'c+');
        if (!$fh) continue;                       // no writable temp folder: no limit rather than no requests
        @flock($fh, LOCK_EX);
        $times = json_decode((string)stream_get_contents($fh), true);
        $times = array_values(array_filter(is_array($times) ? $times : [], fn($t) => is_int($t) && $t > $now - $span));
        if (count($times) >= $limit) $ok = false;
        else $times[] = $now;
        ftruncate($fh, 0);
        rewind($fh);
        fwrite($fh, json_encode($times));
        @flock($fh, LOCK_UN);
        fclose($fh);
        if (!$ok) break;
    }
    return $ok;
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') answer(405, ['ok' => false, 'error' => 'Send the request with POST.']);
$origin = $_SERVER['HTTP_ORIGIN'] ?? '';
if ($origin !== '' && !in_array($origin, ORIGINS, true)) answer(403, ['ok' => false, 'error' => 'Not allowed from this website.']);

$raw = (string)file_get_contents('php://input', false, null, 0, 300000);
$data = json_decode($raw, true);
if (!is_array($data)) answer(400, ['ok' => false, 'error' => 'The request could not be read.']);

// A field people never see or fill in: only robots do. They get a polite answer and nothing is sent.
if (line($data['website'] ?? '', 200) !== '') answer(200, ['ok' => true, 'mailed' => false]);

$c = is_array($data['contact'] ?? null) ? $data['contact'] : [];
$contact = [
    'name'     => line($c['name'] ?? '', 120),
    'company'  => line($c['company'] ?? '', 160),
    'email'    => line($c['email'] ?? '', 160),
    'phone'    => line($c['phone'] ?? '', 60),
    'country'  => line($c['country'] ?? '', 80),
    'location' => line($c['location'] ?? '', 160),
    'notes'    => block($c['notes'] ?? '', 4000),
];
$currency = line($c['currency'] ?? '', 8);
if (!array_key_exists($currency, CURRENCIES)) $currency = '';
if ($contact['name'] === '') answer(400, ['ok' => false, 'error' => 'Enter your name.']);
if (!filter_var($contact['email'], FILTER_VALIDATE_EMAIL)) answer(400, ['ok' => false, 'error' => 'Enter a valid email address.']);

$lines = [];
foreach ((is_array($data['lines'] ?? null) ? $data['lines'] : []) as $l) {
    if (!is_array($l)) continue;
    $qty = filter_var($l['qty'] ?? null, FILTER_VALIDATE_INT, ['options' => ['min_range' => 1, 'max_range' => MAX_QTY]]);
    $code = line($l['cat_nr'] ?? '', 80);
    if ($qty === false || $code === '') answer(400, ['ok' => false, 'error' => 'A product line is not complete.']);
    $id = line($l['id'] ?? '', 160);
    $lines[] = [
        'code'      => $code,
        'ord'       => line($l['ord_nr'] ?? '', 40),
        'title'     => line($l['title'] ?? '', 200),
        'category'  => line($l['category'] ?? '', 80),
        'catalogue' => line($l['catalogue'] ?? '', 120),
        'printed'   => line($l['printed_page'] ?? '', 12),
        'pdf'       => line($l['pdf_page'] ?? '', 12),
        'qty'       => $qty,
        'link'      => preg_match('/^[A-Za-z0-9._-]{1,160}$/', $id) ? SITE . 'p/' . $id . '.html' : '',
    ];
}
if (!$lines) answer(400, ['ok' => false, 'error' => 'Add at least one product to your quote.']);
if (count($lines) > MAX_LINES) answer(400, ['ok' => false, 'error' => 'Too many product lines in one request.']);

$ref = line($data['ref'] ?? '', 20);
if (!preg_match('/^QR-\d{8}-\d{4}$/', $ref)) $ref = 'QR-' . gmdate('Ymd-Hi');
$prepared = line($data['prepared'] ?? '', 60);
$units = array_sum(array_column($lines, 'qty'));

if (!allowed((string)($_SERVER['REMOTE_ADDR'] ?? ''))) {
    answer(429, ['ok' => false, 'error' => 'Too many requests just now. Please try again in a few minutes.']);
}

// ---------------------------------------------------------------- the email
$who = $contact['company'] !== '' ? "{$contact['name']}, {$contact['company']}" : $contact['name'];
$subject = "Quote request {$ref} from {$who}" . ($contact['country'] !== '' ? " ({$contact['country']})" : '');
$received = gmdate('j M Y, H:i') . ' UTC';
$details = [
    'Name' => $contact['name'], 'Company' => $contact['company'], 'Email' => $contact['email'], 'Phone' => $contact['phone'],
    'Country' => $contact['country'], 'Delivery location' => $contact['location'], 'Prices in' => CURRENCIES[$currency],
];

$text = "GROZ QUOTATION REQUEST {$ref}\nSent from the GROZ catalogue website (groz.tools), which is not the official GROZ website.\n"
      . "Received: {$received}" . ($prepared !== '' ? "  (customer's time: {$prepared})" : '') . "\n\nCUSTOMER\n";
foreach ($details as $k => $v) if ($v !== '') $text .= "{$k}: {$v}\n";
$text .= "\nPRODUCTS\n";
foreach ($lines as $n => $l) {
    $text .= ($n + 1) . ". {$l['code']}  |  ORD NR " . ($l['ord'] !== '' ? $l['ord'] : 'not printed in catalogue') . "  |  Quantity {$l['qty']}\n";
    if ($l['title'] !== '') $text .= "   {$l['title']}\n";
    $text .= "   {$l['catalogue']}, printed page " . ($l['printed'] !== '' ? $l['printed'] : 'not printed') . " (PDF page {$l['pdf']})\n";
    if ($l['link'] !== '') $text .= "   {$l['link']}\n";
}
$text .= "\nTotal: " . count($lines) . " product line(s), {$units} unit(s)\n";
if ($contact['notes'] !== '') $text .= "\nNOTES\n{$contact['notes']}\n";
$text .= "\nReply to this email to answer the customer.\n";

$cell = 'padding:8px;border-bottom:1px solid #e7e7ea;vertical-align:top;text-align:left';
$head = 'padding:7px 8px;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#55555b;background:#f5f5f7;border-bottom:2px solid #1d1d1f;text-align:left';
$rows = '';
foreach ($lines as $n => $l) {
    $product = '<b style="font-family:Consolas,monospace">' . h($l['code']) . '</b>'
             . ($l['title'] !== '' ? '<br/>' . h($l['title']) : '')
             . ($l['category'] !== '' ? '<br/><span style="color:#6a6a70">' . h($l['category']) . '</span>' : '')
             . ($l['link'] !== '' ? '<br/><a href="' . h($l['link']) . '">Product page</a>' : '');
    $rows .= '<tr><td style="' . $cell . ';color:#6a6a70">' . ($n + 1) . '</td><td style="' . $cell . '">' . $product . '</td>'
           . '<td style="' . $cell . ';font-family:Consolas,monospace;white-space:nowrap">' . ($l['ord'] !== '' ? h($l['ord']) : '<span style="color:#8a5a00">Not printed</span>') . '</td>'
           . '<td style="' . $cell . '">' . h($l['catalogue']) . '<br/><span style="color:#6a6a70">printed p. ' . h($l['printed'] !== '' ? $l['printed'] : '–') . ' · PDF p. ' . h($l['pdf']) . '</span></td>'
           . '<td style="' . $cell . ';text-align:right;font-weight:bold">' . $l['qty'] . '</td></tr>';
}
$dl = '';
foreach ($details as $k => $v) {
    if ($v === '') continue;
    $value = $k === 'Email' ? '<a href="mailto:' . h($v) . '">' . h($v) . '</a>' : h($v);
    $dl .= '<tr><td style="padding:3px 14px 3px 0;color:#6a6a70;white-space:nowrap">' . h($k) . '</td><td style="padding:3px 0">' . $value . '</td></tr>';
}
$html = '<div style="font-family:Arial,Helvetica,sans-serif;color:#1d1d1f;font-size:14px;line-height:1.45">'
      . '<div style="font-size:20px;font-weight:bold">Quotation request ' . h($ref) . '</div>'
      . '<div style="color:#6a6a70;font-size:12px">Received ' . h($received) . ($prepared !== '' ? ' · customer’s time ' . h($prepared) : '') . ' · from the GROZ catalogue website (not the official GROZ website)</div>'
      . '<div style="height:3px;background:#f4511e;margin:12px 0 16px"></div>'
      . '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-bottom:16px">' . $dl . '</table>'
      . '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">'
      . '<thead><tr><th style="' . $head . '">#</th><th style="' . $head . '">Product</th><th style="' . $head . '">ORD NR</th><th style="' . $head . '">Catalogue</th><th style="' . $head . ';text-align:right">Qty</th></tr></thead>'
      . '<tbody>' . $rows . '</tbody>'
      . '<tfoot><tr><td colspan="4" style="padding:9px 8px;text-align:right;font-weight:bold">' . count($lines) . ' product line(s) · total units</td><td style="padding:9px 8px;text-align:right;font-weight:bold">' . $units . '</td></tr></tfoot></table>'
      . ($contact['notes'] !== '' ? '<div style="margin-top:16px;padding:10px 12px;border-left:3px solid #f4511e;background:#fff6f2"><b>Notes</b><div style="white-space:pre-wrap">' . h($contact['notes']) . '</div></div>' : '')
      . '<p style="color:#6a6a70;font-size:12px;margin-top:18px">Reply to this email to answer the customer. Product data was extracted from GROZ catalogues and has not been verified.</p>'
      . '</div>';

$boundary = 'groz-' . bin2hex(random_bytes(12));
$replyName = trim(str_replace(['"', '\\'], '', $contact['name']));
$headers = 'From: ' . QUOTE_FROM . "\r\n"
         . 'Reply-To: =?UTF-8?B?' . base64_encode($replyName) . '?= <' . $contact['email'] . ">\r\n"
         . "MIME-Version: 1.0\r\n"
         . "Content-Type: multipart/alternative; boundary=\"{$boundary}\"\r\n";
$body = "--{$boundary}\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n"
      . chunk_split(base64_encode($text)) . "\r\n"
      . "--{$boundary}\r\nContent-Type: text/html; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n"
      . chunk_split(base64_encode($html)) . "\r\n"
      . "--{$boundary}--\r\n";

$mailed = @mail(QUOTE_TO, '=?UTF-8?B?' . base64_encode($subject) . '?=', $body, $headers);
answer(200, ['ok' => true, 'mailed' => (bool)$mailed, 'ref' => $ref]);
