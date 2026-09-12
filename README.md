Python-only web service based on DOM-morphing and automatic injection 
Python scripts into the frontend for Ajax, React, or anything else.
=====================================================================

`pip install --force-reinstall git+https://github.com/longnetwork/justbry.git`  


```
python -m uvicorn --log-level debug justbry.demo.bulma:app
python -m uvicorn --log-level debug justbry.demo.dom:app
python -m uvicorn --log-level debug justbry.demo.async:app
python -m uvicorn --log-level debug justbry.demo.morph:app
python -m uvicorn --log-level debug justbry.demo.mlist:app
python -m uvicorn --log-level debug justbry.demo.react:app
python -m uvicorn --log-level debug justbry.demo.widget:app
python -m uvicorn --log-level debug justbry.demo.corsess:app
python -m uvicorn --log-level debug justbry.demo.wnotify:app

```
