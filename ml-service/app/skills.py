"""Small hand-written skill vocabulary used by the keyword baseline.

This is intentionally simple. In week 1 you replace/augment it with an
LLM-based extractor (see docs/MVP_SPEC.md) and keep this as the baseline
you compare against in your evaluation.
"""

# canonical name -> aliases (all lowercase)
SKILLS: dict[str, list[str]] = {
    "Python": ["python"],
    "JavaScript": ["javascript", "js"],
    "TypeScript": ["typescript", "ts"],
    "React": ["react", "react.js", "reactjs"],
    "Next.js": ["next.js", "nextjs"],
    "Node.js": ["node.js", "nodejs", "node"],
    "NestJS": ["nestjs", "nest.js"],
    "FastAPI": ["fastapi"],
    "Django": ["django"],
    "Flask": ["flask"],
    "PostgreSQL": ["postgresql", "postgres"],
    "MySQL": ["mysql"],
    "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis"],
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes", "k8s"],
    "AWS": ["aws", "amazon web services"],
    "Git": ["git", "github"],
    "CI/CD": ["ci/cd", "github actions", "continuous integration"],
    "REST APIs": ["rest api", "rest apis", "restful"],
    "GraphQL": ["graphql"],
    "SQL": ["sql"],
    "Machine Learning": ["machine learning", "ml"],
    "Deep Learning": ["deep learning"],
    "NLP": ["nlp", "natural language processing"],
    "PyTorch": ["pytorch"],
    "TensorFlow": ["tensorflow"],
    "scikit-learn": ["scikit-learn", "sklearn"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "LLMs": ["llm", "llms", "large language model", "large language models"],
    "RAG": ["rag", "retrieval-augmented generation"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3", "tailwind", "tailwindcss"],
    "React Native": ["react native"],
    "Testing": ["unit testing", "jest", "pytest", "testing"],
    "Agile": ["agile", "scrum"],
}
