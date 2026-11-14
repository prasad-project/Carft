"""Categorised skill dictionary. Keys are schema category names."""
SKILLS = {
    "programming_languages": [
        "Python", "Java", "C++", "C#", "C", "JavaScript", "TypeScript", "SQL", "PL/SQL", "Go", "Rust", "Kotlin",
        "Swift", "PHP", "Ruby", "Scala", "R", "MATLAB", "Dart", "Perl", "Bash", "Shell Scripting", "HTML",
        "HTML5", "CSS", "CSS3", "SASS", "SCSS", "Objective-C", "Haskell", "Julia", "Lua", "VBA", "Solidity",
        "Assembly", "NoSQL"],
    "frameworks": [
        "React", "Next.js", "Angular", "Vue.js", "Svelte", "Django", "Flask", "FastAPI", "Spring Boot",
        "Spring", "Express.js", "Express", "NestJS", "Laravel", "Ruby on Rails", "ASP.NET", ".NET",
        "Bootstrap", "Tailwind CSS", "Streamlit", "Gradio", "Flutter", "React Native", "Node.js", "Redux",
        "Hibernate", "Nuxt.js", "Gatsby", "Electron", "Django REST Framework", "Quarkus", "Micronaut"],
    "libraries": [
        "Pandas", "NumPy", "SciPy", "Matplotlib", "Seaborn", "Plotly", "OpenCV", "NLTK", "spaCy",
        "Beautiful Soup", "Requests", "Pydantic", "SQLAlchemy", "jQuery", "Pillow", "Polars", "Dask",
        "Lodash", "Axios", "Celery", "Scrapy", "Tesseract", "PyMuPDF", "Selenium", "Pygame", "Tkinter",
        "Hugging Face Transformers", "Transformers", "Statsmodels", "Pytest", "Jest"],
    "databases": [
        "PostgreSQL", "MySQL", "MongoDB", "Redis", "SQLite", "Oracle", "SQL Server", "MariaDB", "Cassandra",
        "DynamoDB", "Elasticsearch", "Firebase", "Supabase", "Neo4j", "Snowflake", "BigQuery", "Pinecone",
        "ChromaDB", "FAISS", "Milvus", "Weaviate", "CouchDB", "Redshift", "Vector Databases", "Qdrant"],
    "developer_tools": [
        "Git", "GitHub", "GitLab", "Bitbucket", "Docker", "Kubernetes", "Jenkins", "VS Code", "Postman", "Jira",
        "CI/CD", "Terraform", "Ansible", "Figma", "Swagger", "Maven", "Gradle", "npm", "Webpack", "Vite",
        "Jupyter", "Jupyter Notebook", "GitHub Actions", "Nginx", "IntelliJ", "PyCharm", "Eclipse", "Confluence",
        "Selenium", "Linux Shell", "Google Colab", "Android Studio", "Prometheus", "Grafana", "Trello", "Notion"],
    "cloud": [
        "AWS", "Azure", "GCP", "Google Cloud", "Google Cloud Platform", "Heroku", "Vercel", "Netlify",
        "DigitalOcean", "EC2", "S3", "AWS Lambda", "Lambda", "Cloud Run", "Cloudflare", "Amazon Web Services",
        "Microsoft Azure", "SageMaker", "Vertex AI", "Azure DevOps", "CloudFormation"],
    "ai_ml": [
        "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "XGBoost", "LightGBM", "LangChain", "LlamaIndex",
        "RAG", "Generative AI", "LLM", "LLMs", "Agentic AI", "NLP", "Natural Language Processing",
        "Computer Vision", "Deep Learning", "Machine Learning", "Reinforcement Learning", "OpenAI",
        "Hugging Face", "Prompt Engineering", "MLOps", "Neural Networks", "YOLO", "CNN", "RNN", "LSTM", "BERT",
        "GPT", "Stable Diffusion", "LangGraph", "CrewAI", "AutoGen", "Data Science", "Artificial Intelligence",
        "Fine-tuning", "Time Series", "Recommendation Systems", "Ollama", "MLflow"],
    "data_analytics": [
        "Power BI", "Tableau", "Excel", "Advanced Excel", "Looker", "Looker Studio", "Google Analytics",
        "Data Visualization", "Data Analysis", "ETL", "Alteryx", "SAS", "SPSS", "Qlik", "QlikView",
        "Apache Spark", "Spark", "PySpark", "Hadoop", "Airflow", "Apache Airflow", "Kafka", "Apache Kafka", "dbt",
        "Statistics", "Statistical Analysis", "A/B Testing", "Data Mining", "Data Wrangling", "Hive", "Databricks",
        "Data Warehousing", "Google Sheets", "Metabase", "Data Cleaning", "EDA", "Business Intelligence"],
    "operating_systems": [
        "Linux", "Ubuntu", "Windows", "macOS", "Unix", "Debian", "CentOS", "Red Hat", "Fedora", "Android",
        "iOS", "Kali Linux", "Windows Server"],
    "soft_skills": [
        "Communication", "Leadership", "Teamwork", "Problem Solving", "Problem-Solving", "Critical Thinking",
        "Time Management", "Adaptability", "Creativity", "Collaboration", "Project Management", "Public Speaking",
        "Negotiation", "Decision Making", "Conflict Resolution", "Presentation Skills", "Mentoring",
        "Analytical Thinking", "Emotional Intelligence", "Work Ethic", "Attention to Detail", "Team Management",
        "Stakeholder Management", "Interpersonal Skills", "Self-motivated", "Fast Learner", "Active Listening",
        "Strategic Thinking", "Multitasking", "Organization", "Verbal Communication", "Written Communication"],
    "other": [
        "REST API", "REST APIs", "RESTful APIs", "GraphQL", "Microservices", "Agile", "Scrum", "OOP",
        "Object-Oriented Programming", "Data Structures", "Algorithms", "DSA", "System Design", "Web Development",
        "Unit Testing", "TDD", "API Development", "Responsive Design", "Cybersecurity", "Blockchain", "IoT",
        "WebSockets", "OAuth", "JWT", "Design Patterns", "Software Testing", "DevOps", "Kanban", "UI/UX",
        "gRPC", "Web Scraping", "Embedded Systems", "Networking", "Version Control", "Low Level Design",
        "High Level Design", "SDLC", "Test Automation", "Automation Testing", "Manual Testing"],
}

ALIASES = {
    "js": "JavaScript", "ts": "TypeScript", "nodejs": "Node.js", "node": "Node.js", "reactjs": "React",
    "react.js": "React", "vuejs": "Vue.js", "vue": "Vue.js", "nextjs": "Next.js", "postgres": "PostgreSQL",
    "mongo": "MongoDB", "sklearn": "Scikit-learn", "scikit learn": "Scikit-learn", "scikit-learn": "Scikit-learn",
    "powerbi": "Power BI", "power-bi": "Power BI", "k8s": "Kubernetes", "genai": "Generative AI",
    "gen ai": "Generative AI", "ml": "Machine Learning", "dl": "Deep Learning", "springboot": "Spring Boot",
    "tailwind": "Tailwind CSS", "tailwindcss": "Tailwind CSS", "expressjs": "Express.js", "vs code": "VS Code",
    "vscode": "VS Code", "ms excel": "Excel", "microsoft excel": "Excel", "mssql": "SQL Server",
    "ms sql": "SQL Server", "my sql": "MySQL", "c plus plus": "C++", "cpp": "C++", "py": "Python",
    "pytorch lightning": "PyTorch", "opencv-python": "OpenCV", "tf": "TensorFlow", "huggingface": "Hugging Face",
    "bs4": "Beautiful Soup", "problem solving skills": "Problem Solving", "team work": "Teamwork",
    "rest": "REST API", "restful api": "REST APIs", "oops": "OOP", "oop concepts": "OOP",
    "data structures and algorithms": "DSA", "data structure": "Data Structures", "cicd": "CI/CD",
    "aws cloud": "AWS", "ms office": "Microsoft Office", "html/css": "HTML", "css/html": "HTML",
}

# Short / ambiguous names: matched case-sensitively and ONLY inside a skills section.
AMBIGUOUS = {"C", "R", "Go", "Express", "Spring", "Lambda", "S3", "Spark", "Notion", "Excel", "Transformers",
              "Requests", "Windows", "Android", "GPT", "Organization", "Communication", "Leadership", "Teamwork",
              "Statistics", "Algorithms", "Networking", "Data Science", "Presentation Skills"}
