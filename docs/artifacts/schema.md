

```mermaid
erDiagram
  "fields" {    
    BIGINT id PK "in index: ix_fields_id"    
    TEXT display_name      
    BIGINT domain FK 
  }
  "domains" {    
    BIGINT id PK "in index: ix_domains_id"    
    TEXT display_name  
  }
  "works" {    
    BIGINT id PK "in index: ix_works_id"    
    TEXT doi      
    TEXT title      
    TEXT display_name      
    BIGINT publication_year      
    TEXT type  
  }
  "works-authorships" {    
    BIGINT parent_id FK     
    BIGINT author FK     
    BIGINT institution FK 
  }
  "authors" {    
    BIGINT id PK "in index: ix_authors_id"    
    TEXT orcid      
    TEXT display_name  
  }
  "institutions" {    
    BIGINT id PK "in index: ix_institutions_id"    
    TEXT display_name      
    TEXT country_code      
    TEXT display_name_acronyms  
  }
  "subfields" {    
    BIGINT id PK "in index: ix_subfields_id"    
    TEXT display_name      
    BIGINT field FK 
  }
  "works-locations" {    
    BIGINT parent_id FK     
    BIGINT source FK 
  }
  "sources" {    
    BIGINT id PK "in index: ix_sources_id"    
    TEXT display_name      
  }
  "works-referenced_works" {    
    BIGINT parent_id FK     
    BIGINT referenced_work_id FK 
  }
  "works-topics" {    
    BIGINT parent_id FK     
    BIGINT id      
    DOUBLE PRECISION score  
  }
  "topics" {    
    BIGINT id PK "in index: ix_topics_id"    
    TEXT display_name      
    BIGINT subfield FK     
    BIGINT field FK     
    BIGINT domain FK 
  }
  "fields" ||--|{ "domains" : "domain -> id"
  "works-authorships" ||--|{ "works" : "parent_id -> id"
  "works-authorships" ||--|{ "institutions" : "institution -> id"
  "works-authorships" ||--|{ "authors" : "author -> id"
  "subfields" ||--|{ "fields" : "field -> id"
  "works-locations" ||--|{ "works" : "parent_id -> id"
  "works-locations" ||--|{ "sources" : "source -> id"
  "works-referenced_works" ||--|{ "works" : "parent_id -> id; referenced_work_id -> id"
  "works-topics" ||--|{ "works" : "parent_id -> id"
  "topics" ||--|{ "subfields" : "subfield -> id"
  "topics" ||--|{ "fields" : "field -> id"
  "topics" ||--|{ "domains" : "domain -> id"
```

