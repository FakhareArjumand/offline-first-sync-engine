import 'dart:convert';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:uuid/uuid.dart';
import '../lib/core/sync_engine.dart';

Future<void> main() async {
  // 1. Initialize SQLite FFI (Required for Flutter Desktop / Dart CLI)
  sqfliteFfiInit();
  var databaseFactory = databaseFactoryFfi;
  
  // We use an in-memory DB for the demo so it resets clean every run
  var db = await databaseFactory.openDatabase(inMemoryDatabasePath);

  print("🟢 [LOCAL] SQLite Database initialized");

  // 2. Create the Local Tables
  await db.execute('''
    CREATE TABLE IF NOT EXISTS documents (
      id TEXT PRIMARY KEY,
      title TEXT,
      content TEXT,
      updated_at TEXT
    )
  ''');

  await db.execute('''
    CREATE TABLE IF NOT EXISTS sync_queue (
      id TEXT PRIMARY KEY,
      table_name TEXT,
      action TEXT,
      payload TEXT,
      updated_at TEXT
    )
  ''');

  // 3. Simulate an offline user action (Creating a document)
  var uuid = const Uuid();
  var docId = uuid.v4();
  var now = DateTime.now().toUtc().toIso8601String();

  var docPayload = {
    'id': docId,
    'title': 'Arjumand Labs Master Plan',
    'content': 'Taking over GitHub one repo at a time.',
    'updated_at': now
  };

  // Insert into the local database (App updates instantly for the user)
  await db.insert('documents', docPayload);
  
  // Intercept the mutation and save it to the offline queue
  await db.insert('sync_queue', {
    'id': docId, 
    'table_name': 'documents',
    'action': 'INSERT',
    'payload': jsonEncode(docPayload),
    'updated_at': now
  });

  print("📄 [LOCAL] Inserted offline document: \${docPayload['title']}");

  // 4. Fetch the queue to prepare for sync
  var rawQueue = await db.query('sync_queue');
  
  // Parse the payload strings back to JSON objects for the HTTP request
  List<Map<String, dynamic>> syncPayload = rawQueue.map((row) {
    var mutableRow = Map<String, dynamic>.from(row);
    mutableRow['payload'] = jsonDecode(mutableRow['payload'] as String);
    return mutableRow;
  }).toList();

  print("🚀 [NETWORK] Pushing \${syncPayload.length} mutations to Python Server...");

  // 5. Fire the Sync Engine
  var engine = SyncEngine(
    serverUrl: 'http://localhost:8000', // Changed from 127.0.0.1
    clientId: 'macbook-m3-client',
  );

  // We pass a fake "last sync time" of 2024 to simulate a client catching up
  await engine.pushLocalQueue(syncPayload, "2024-01-01T00:00:00Z");

  await db.close();
}