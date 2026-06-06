[中文](bookmarklet-quickstart.md) | English

# Bookmarklet Quick Start

## Fastest Path

### 1. Start The GUI

```powershell
python -m flowscribe.gui
```

### 2. Enable The Server

1. click `Queue` in the top toolbar
2. enable `Server`
3. confirm the running status such as `Server: Running on port 8765`

### 3. Install The Bookmarklet

1. open `http://127.0.0.1:8765/bookmarklet.js`
2. copy the generated code
3. create a browser bookmark:
   - open your bookmarks manager
   - create a new bookmark
   - name it `FlowScribe`
   - paste the copied code as the URL

### 4. Use It

1. open any video page such as YouTube or Bilibili
2. click the `FlowScribe` bookmarklet
3. you should see a message like `Added to FlowScribe queue`
4. return to the GUI and confirm the new URL appears in `Queue`
5. click `Start Queue`

## Full Bookmarklet Code

If automatic generation is not available, you can copy this manually:

```javascript
javascript:(function(){var url=window.location.href;var title=document.title;fetch('http://127.0.0.1:8765/add-url',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:url,title:title,timestamp:new Date().toISOString()})}).then(r=>r.json()).then(d=>{if(d.status==='queued'){alert('✓ Added to FlowScribe queue\nPosition: '+d.position);}else if(d.status==='duplicate'){alert('⚠ Already in queue: '+d.existing_status);}else{alert('✗ Error: '+d.message);}}).catch(e=>alert('✗ Connection failed. Is FlowScribe server running?'));})();
```

## Common Questions

**Q: The bookmarklet says "Connection failed"**

- make sure the GUI server is enabled
- or run `python -m flowscribe serve`

**Q: The port is already in use**

- change the port in the GUI server section
- enable the server again

**Q: How do I change output settings**

- update output directory, format, model, or language in the GUI
- newly added URLs will use the updated defaults

## More Docs

- [bookmarklet.md](bookmarklet.md) - Chinese bookmarklet guide
- [bookmarklet-en.md](bookmarklet-en.md) - full bookmarklet guide
- [server-configuration.md](server-configuration.md) - server configuration (`English only for now`)
