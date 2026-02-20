import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { SSEServerTransport } from '@modelcontextprotocol/sdk/server/sse.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import * as vectordb from 'vectordb';
import path from 'path';
import { fileURLToPath } from 'url';
import express from 'express';
import { createServer } from 'http';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DB_PATH = path.join(__dirname, '.memory');

const PORT = process.env.PORT || 7500;

class MemoryServer {
  constructor() {
    this.server = new Server(
      { name: 'memory-server', version: '1.0.0' },
      { capabilities: { tools: {} } }
    );
    
    this.db = null;
    this.table = null;
    
    this.setupTools();
  }
  
  async ensureTable() {
    if (this.table) return;
    
    try {
      this.db = await vectordb.connect(DB_PATH);
      
      try {
        this.table = await this.db.openTable('memories');
      } catch {
        this.table = await this.db.createTable('memories', [
          { id: "_init_", content: "_init_", memory_type: "system", tags: "", source_agent: "system", vector: this.getEmbedding("_init_") }
        ]);
      }
      
      console.error("Memory table initialized");
    } catch (e) {
      console.error("Init error:", e.message);
    }
  }
  
  getEmbedding(text) {
    const hash = text.split('').reduce((a, b) => {
      a = ((a << 5) - a) + b.charCodeAt(0);
      return a & a;
    }, 0);
    const vector = [];
    let seed = Math.abs(hash);
    for (let i = 0; i < 384; i++) {
      seed = (seed * 1103515245 + 12345) & 0x7fffffff;
      vector.push((seed / 0x7fffffff) * 2 - 1);
    }
    return vector;
  }
  
  setupTools() {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      return {
        tools: [
          {
            name: "memory_add",
            description: "Add a memory to the vector store",
            inputSchema: {
              type: "object",
              properties: {
                content: { type: "string", description: "Content to store" },
                memory_type: { type: "string", description: "Type of memory", default: "context" },
                tags: { type: "array", items: { type: "string" }, description: "Tags", default: [] },
                source_agent: { type: "string", description: "Source agent", default: "unknown" }
              },
              required: ["content"]
            }
          },
          {
            name: "memory_query",
            description: "Query memories by semantic similarity",
            inputSchema: {
              type: "object",
              properties: {
                query: { type: "string", description: "Search query" },
                memory_type: { type: "string", description: "Filter by type", default: null },
                limit: { type: "number", description: "Max results", default: 10 }
              },
              required: ["query"]
            }
          },
          {
            name: "memory_count",
            description: "Count total memories",
            inputSchema: { type: "object", properties: {} }
          },
          {
            name: "memory_clear",
            description: "Clear all memories",
            inputSchema: { type: "object", properties: {} }
          }
        ]
      };
    });
    
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;
      
      try {
        await this.ensureTable();
        
        if (name === "memory_add") {
          const id = crypto.randomUUID();
          const { content, memory_type = "context", tags = [], source_agent = "unknown" } = args;
          
          await this.table.add([{
            id,
            content,
            memory_type,
            tags: tags.join(','),
            source_agent,
            vector: this.getEmbedding(content)
          }]);
          
          return { content: [{ type: "text", text: JSON.stringify({ memory_id: id, status: "added" }) }] };
        }
        
        if (name === "memory_query") {
          const { query, memory_type, limit = 10 } = args;
          
          const results = await this.table.search(this.getEmbedding(query)).limit(limit).execute();
          
          let memories = results
            .filter(r => r.id !== "_init_")
            .map(r => ({
              id: r.id,
              content: r.content,
              memory_type: r.memory_type,
              tags: r.tags,
              source_agent: r.source_agent,
              distance: r._distance
            }));
          
          return { content: [{ type: "text", text: JSON.stringify(memories) }] };
        }
        
        if (name === "memory_count") {
          const results = await this.table.search(this.getEmbedding("")).limit(1000).execute();
          const count = results.filter(r => r.id !== "_init_").length;
          return { content: [{ type: "text", text: JSON.stringify({ count }) }] };
        }
        
        if (name === "memory_clear") {
          try { await this.db.dropTable('memories'); } catch {}
          this.table = await this.db.createTable('memories', [
            { id: "_init_", content: "_init_", memory_type: "system", tags: "", source_agent: "system", vector: this.getEmbedding("_init_") }
          ]);
          return { content: [{ type: "text", text: JSON.stringify({ status: "cleared" }) }] };
        }
        
        return { content: [{ type: "text", text: JSON.stringify({ error: "Unknown tool" }) }] };
      } catch (e) {
        return { content: [{ type: "text", text: JSON.stringify({ error: e.message }) }] };
      }
    });
  }
  
  async runStdio() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error("Memory MCP server running on stdio");
  }
  
  async runSSE() {
    const app = express();
    const transport = new SSEServerTransport('/messages/');
    
    app.get('/sse', async (req, res) => {
      await transport.connect(req, res);
    });
    
    app.post('/messages', async (req, res) => {
      await transport.handlePostMessage(req, res);
    });
    
    app.get('/health', (req, res) => {
      res.json({ status: 'ok', tools: ['memory_add', 'memory_query', 'memory_count', 'memory_clear'] });
    });
    
    // REST API for testing
    app.use(express.json());
    
    app.post('/memory/add', async (req, res) => {
      await this.ensureTable();
      const id = crypto.randomUUID();
      const { content, memory_type = "context", tags = [], source_agent = "unknown" } = req.body;
      await this.table.add([{ id, content, memory_type, tags: tags.join(','), source_agent, vector: this.getEmbedding(content) }]);
      res.json({ memory_id: id, status: "added" });
    });
    
    app.post('/memory/query', async (req, res) => {
      await this.ensureTable();
      const { query, limit = 10 } = req.body;
      const results = await this.table.search(this.getEmbedding(query)).limit(limit).execute();
      const memories = results.filter(r => r.id !== "_init_").map(r => ({ id: r.id, content: r.content, memory_type: r.memory_type, distance: r._distance }));
      res.json(memories);
    });
    
    app.get('/memory/count', async (req, res) => {
      await this.ensureTable();
      const results = await this.table.search(this.getEmbedding("")).limit(1000).execute();
      const count = results.filter(r => r.id !== "_init_").length;
      res.json({ count });
    });
    
    app.post('/memory/clear', async (req, res) => {
      await this.db.dropTable('memories').catch(() => {});
      this.table = await this.db.createTable('memories', [{ id: "_init_", content: "_init_", memory_type: "system", tags: "", source_agent: "system", vector: this.getEmbedding("_init_") }]);
      res.json({ status: "cleared" });
    });
    
    const server = createServer(app);
    server.listen(PORT, () => {
      console.error(`Memory MCP server running on http://127.0.0.1:${PORT}`);
    });
  }
  
  async run() {
    const mode = process.env.MODE || 'stdio';
    
    if (mode === 'sse') {
      await this.runSSE();
    } else {
      await this.runStdio();
    }
  }
}

const server = new MemoryServer();
server.run().catch(console.error);
