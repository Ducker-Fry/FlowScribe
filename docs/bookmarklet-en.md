[中文](bookmarklet.md) | English

# Bookmarklet Integration Guide

FlowScribe supports a browser bookmarklet that sends video or audio page URLs into the transcription queue.

## Quick Start

### Option 1: GUI Built-In Server

1. start the GUI:

   ```powershell
   python -m flowscribe.gui
   ```

2. open `Queue` from the top toolbar
3. enable `Server`
4. visit `http://127.0.0.1:8765/bookmarklet.js`
5. copy the generated JavaScript
6. create a bookmark whose URL is the copied script
7. browse a video page, click the bookmarklet, and return to `Queue`

### Option 2: CLI Server

```powershell
python -m flowscribe serve
```

or with custom settings:

```powershell
python -m flowscribe serve -o E:\Transcripts --format txt,srt -m medium -l zh
```

Then install the bookmarklet the same way and optionally open the GUI to process the queue.

## Bookmarklet Script

### Recommended Way To Get It

1. start the GUI or CLI server
2. open `http://127.0.0.1:8765/bookmarklet.js`
3. copy the generated script

### Manual Script

```javascript
javascript:(function(){var url=window.location.href;var title=document.title;fetch('http://127.0.0.1:8765/add-url',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:url,title:title,timestamp:new Date().toISOString()})}).then(r=>r.json()).then(d=>{if(d.status==='queued'){alert('✓ Added to FlowScribe queue\nPosition: '+d.position);}else if(d.status==='duplicate'){alert('⚠ Already in queue: '+d.existing_status);}else{alert('✗ Error: '+d.message);}}).catch(e=>alert('✗ Connection failed. Is FlowScribe server running?'));})();
```

## What The Script Does

The bookmarklet:

1. reads the current page URL
2. reads the current page title
3. sends both to `http://127.0.0.1:8765/add-url`
4. shows a success, duplicate, or failure message

## Typical Usage

### GUI-Oriented Flow

1. start the GUI
2. open `Queue`
3. enable `Server`
4. browse a page
5. click the bookmarklet
6. return to the GUI and run `Start Queue`

### Batch Collection Flow

1. browse multiple pages
2. click the bookmarklet on each page
3. build up a queue
4. process them together later

## Configuration Notes

### GUI Server Configuration

The built-in server uses current GUI defaults for:

- output directory
- output formats
- model
- language

### CLI Server Configuration

```powershell
python -m flowscribe serve
python -m flowscribe serve -o E:\Transcripts
python -m flowscribe serve --format txt,md,srt
python -m flowscribe serve -m medium -l zh
python -m flowscribe serve -o E:\Videos\Transcripts --format txt,srt -m small -l zh --port 9000
```

## API Endpoints

- `POST /add-url`
- `POST /add-urls`
- `GET /status`
- `GET /bookmarklet.js`

## Safety Notes

- the server listens on `127.0.0.1` by default
- URL validation blocks private and unsafe target addresses
- it accepts HTTP and HTTPS URLs only
- bookmarklet support is for normal local workflows, not for bypassing access restrictions

## Troubleshooting

### Connection Failed

- confirm the server is running
- check that the port matches
- verify `http://127.0.0.1:8765/status`

### Port Already In Use

- choose another port in the GUI
- or run `python -m flowscribe serve --port 9000`

### URL Rejected

Typical reasons:

- private IP address
- unsupported protocol
- invalid URL format

### Queue Does Not Refresh In The GUI

- restart the GUI
- confirm file permissions for the queue file
- try adding another URL to force a refresh

## Related Docs

- [bookmarklet-quickstart-en.md](bookmarklet-quickstart-en.md) - fastest setup path
- [server-configuration.md](server-configuration.md) - detailed server options (`English only for now`)
- [server-output-example.md](server-output-example.md) - server output examples (`Chinese only for now`)
