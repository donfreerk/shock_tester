# Temporäre Log-Ausgabe - Service Testing
# Diese Datei kann sicher gelöscht werden

(shock_tester) PS C:\WorkDir\shock_tester> python -m backend.can_simulator_service.main
2025-06-24 10:08:43,511 - __main__ - INFO - Starte EGEA CAN-Simulator Service...
2025-06-24 10:08:43,511 - __main__ - INFO - Konfiguration: damping_quality=good, freq_range=25.0-2.0Hz, amplitude=6.0mm
2025-06-24 10:08:43,511 - __main__ - INFO - ⏳ Warte auf MQTT-Commands zum Starten von Tests
--- Logging error ---
Traceback (most recent call last):
  File "C:\Users\HSaathoff\AppData\Local\Programs\Python\Python313\Lib\logging\__init__.py", line 1153, in emit
    stream.write(msg + self.terminator)
    ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\HSaathoff\AppData\Local\Programs\Python\Python313\Lib\encodings\cp1252.py", line 19, in encode
    return codecs.charmap_encode(input,self.errors,encoding_table)[0]
           ~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
UnicodeEncodeError: 'charmap' codec can't encode character '\u23f3' in position 44: character maps to <undefined>
Call stack:
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\WorkDir\shock_tester\backend\can_simulator_service\main.py", line 408, in <module>
    asyncio.run(main())
  File "C:\Users\HSaathoff\AppData\Local\Programs\Python\Python313\Lib\asyncio\runners.py", line 195, in run
    return runner.run(main)
  File "C:\Users\HSaathoff\AppData\Local\Programs\Python\Python313\Lib\asyncio\runners.py", line 118, in run
    return self._loop.run_until_complete(task)
  File "C:\Users\HSaathoff\AppData\Local\Programs\Python\Python313\Lib\asyncio\base_events.py", line 706, in run_until_complete
    self.run_forever()
  File "C:\Users\HSaathoff\AppData\Local\Programs\Python\Python313\Lib\asyncio\base_events.py", line 677, in run_forever
    self._run_once()
  File "C:\Users\HSaathoff\AppData\Local\Programs\Python\Python313\Lib\asyncio\base_events.py", line 2034, in _run_once
    handle._run()
  File "C:\Users\HSaathoff\AppData\Local\Programs\Python\Python313\Lib\asyncio\events.py", line 89, in _run
    self._context.run(self._callback, *self._args)
  File "C:\WorkDir\shock_tester\backend\can_simulator_service\main.py", line 390, in main
    logger.info("⏳ Warte auf MQTT-Commands zum Starten von Tests")
Message: '⏳ Warte auf MQTT-Commands zum Starten von Tests'
Arguments: ()
