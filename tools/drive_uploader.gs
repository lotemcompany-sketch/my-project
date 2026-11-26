/**
 * BeatCut — מעלה אישי לדרייב.
 * מאפשר ל-Claude להעלות סרטונים גדולים רק לתיקיות BeatCut שלך.
 * הסקריפט לא מעלה קבצים בעצמו: הוא פותח "חלון העלאה" חד-פעמי לקובץ אחד,
 * ו-Claude שולח את הקובץ ישירות לגוגל דרך החלון הזה.
 */
const KEY = 'PUT-YOUR-SECRET-KEY-HERE';
const ALLOWED = {
  'BeatCut': '1d_zhnaaYaWMQPbKqQCXqpDL3BmN1gbhZ',
  'ריקוד': '1bCkT_yiJ2bEae52hvMsi0TZ5QQNt7og0',
  'ספורט': '1XrIhp7DRw9bNqqzH3p8rGjO2lyl-v5uy',
  'מוכנים': '15qWegtYKxNShKb8x8oR6rzahky-WYzZk',
};

function doPost(e) {
  const d = JSON.parse(e.postData.contents || '{}');
  if (d.key !== KEY) return out({ ok: false, error: 'bad key' });
  const folderId = d.folder || ALLOWED['מוכנים'];
  if (Object.values(ALLOWED).indexOf(folderId) < 0) return out({ ok: false, error: 'folder not allowed' });
  DriveApp.getFolderById(folderId); // מוודא שהתיקייה קיימת
  const res = UrlFetchApp.fetch('https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable', {
    method: 'post',
    contentType: 'application/json; charset=UTF-8',
    headers: {
      Authorization: 'Bearer ' + ScriptApp.getOAuthToken(),
      'X-Upload-Content-Type': d.mimeType || 'video/mp4',
      'X-Upload-Content-Length': String(d.size),
    },
    payload: JSON.stringify({ name: d.name, parents: [folderId] }),
    muteHttpExceptions: true,
  });
  const loc = res.getHeaders()['Location'] || res.getHeaders()['location'];
  if (!loc) return out({ ok: false, error: res.getContentText() });
  return out({ ok: true, uploadUrl: loc });
}

function doGet() { return out({ ok: true, service: 'BeatCut uploader' }); }
function out(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }
