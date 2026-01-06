lens-search/
├── README.md
├── .gitignore
├── docker-compose.yml                # optional (local dev for web+api)
│
├── frontend/                         # Next.js app (frontend + BFF endpoints if needed)
│   ├── package.json
│   ├── next.config.js
│   ├── tsconfig.json
│   ├── .env.local.example
│   ├── public/
│   │   └── images/                   # static image dataset served by Next.js
│   │       ├── sample/
│   │       └── full/
│   │
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx              # main search page
│   │   │   ├── results/page.tsx      # optional dedicated results page
│   │   │   └── api/
│   │   │       └── proxy-search/route.ts  # optional: proxy to FastAPI (avoid CORS)
│   │   │
│   │   ├── components/
│   │   │   ├── SearchBar.tsx
│   │   │   ├── ResultsGrid.tsx
│   │   │   ├── ResultCard.tsx
│   │   │   └── QueryExamples.tsx
│   │   │
│   │   ├── lib/
│   │   │   ├── api.ts                # typed fetch() wrappers
│   │   │   └── types.ts              # shared TS types for API responses
│   │   │
│   │   └── styles/                   # optional
│   │
│   └── tests/                        # optional
│
├── api/                              # FastAPI service (CLIP embed + search)
│   ├── pyproject.toml                # or requirements.txt
│   ├── requirements.txt              # if you prefer pip
│   ├── .env.example
│   ├── Dockerfile                    # optional
│   │
│   ├── app/
│   │   ├── main.py                   # FastAPI entry
│   │   ├── config.py                 # env config (paths, K, model name)
│   │   ├── routes/
│   │   │   ├── health.py             # GET /health
│   │   │   ├── search.py             # POST /search (query -> topK)
│   │   │   └── ingest.py             # optional: build embeddings index
│   │   │
│   │   ├── services/
│   │   │   ├── clip_model.py         # loads CLIP, encodes text/images
│   │   │   ├── index_store.py         # loads/saves embeddings.npy + ids.json
│   │   │   └── similarity.py         # cosine sim, topK selection
│   │   │
│   │   ├── schemas/
│   │   │   ├── search.py             # Pydantic request/response models
│   │   │   └── ingest.py
│   │   │
│   │   └── utils/
│   │       ├── image_io.py            # reading images if ingest is used
│   │       └── timing.py
│   │
│   └── scripts/
│       ├── embed_images.py           # offline embedding build (recommended)
│       └── smoke_test.py             # quick sanity checks
│
├── artifacts/                        # generated + cached assets (commit lightly)
│   ├── embeddings/
│   │   ├── image_embeddings.npy
│   │   ├── image_ids.json
│   │   └── metadata.json             # optional: image size, model version, date
│   │
│   └── evaluation/
│       ├── eval_labels.csv           # small labeled subset for Recall@K
│       └── metrics.json
│
├── evaluation/                       # experiments + metrics (not core app)
│   ├── analysis.ipynb                # plots + prompt tests + failure cases
│   ├── evaluate_recall.py            # compute Recall@K
│   └── failure_cases.md              # curated failure examples + explanations
│
└── docs/                             # polish for recruiters
    ├── architecture.png              # diagram of web ↔ api ↔ embeddings
    ├── demo.gif                      # short demo clip
    └── screenshots/
        ├── search.png
        └── results.png
