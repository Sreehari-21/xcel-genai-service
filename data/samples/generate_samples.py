import pymupdf
import pandas as pd

# 1. Generate DBMS.pdf
doc = pymupdf.open()

# Page 1: Introduction to Normalization
page1 = doc.new_page()
text_p1 = """Database Systems & Design
Chapter 5: Relational Database Normalization

1. Introduction to Normalization
Normalization is the systematic approach of decomposing database tables to eliminate data redundancy and undesired insertion, update, and deletion anomalies. It was formulated by Edgar F. Codd as part of the relational database model.

Key Goals of Normalization:
- Minimizing duplicate data across tables
- Ensuring data integrity and consistency
- Enforcing functional dependencies and referential constraints
- Optimizing database storage and transactional integrity

2. Database Anomalies
Without normalization, databases suffer from three classical anomalies:
- Insertion Anomaly: Inability to record certain information without adding extraneous unrelated data.
- Deletion Anomaly: Loss of critical unintended data when deleting a record.
- Update Anomaly: Inconsistent updates across duplicate rows leading to data divergence.
"""
page1.insert_text((50, 60), text_p1, fontsize=11)

# Page 2: Normal Forms 1NF and 2NF
page2 = doc.new_page()
text_p2 = """Chapter 5: Relational Database Normalization (Continued)

3. First Normal Form (1NF)
A relation is in First Normal Form (1NF) if and only if:
- Every attribute contains only atomic (indivisible) values.
- There are no repeating groups or multivalued attributes.
- Each record is uniquely identified by a primary key.

4. Second Normal Form (2NF)
A relation is in Second Normal Form (2NF) if:
- It meets all criteria for First Normal Form (1NF).
- No non-prime attribute is partially dependent on any candidate key.
In other words, all non-key attributes must be fully functionally dependent on the entire primary key, not a proper subset of a composite key.
"""
page2.insert_text((50, 60), text_p2, fontsize=11)

# Page 3: Third Normal Form (3NF) & BCNF
page3 = doc.new_page()
text_p3 = """Chapter 5: Relational Database Normalization (Continued)

5. Third Normal Form (3NF)
A relation is in Third Normal Form (3NF) if:
- It satisfies Second Normal Form (2NF).
- No non-prime attribute is transitively dependent on the primary key.
Transitive dependency exists when X -> Y and Y -> Z, meaning non-key attribute Z depends on non-key attribute Y which depends on candidate key X.

6. Boyce-Codd Normal Form (BCNF)
Boyce-Codd Normal Form (BCNF) is a stricter version of 3NF.
A relation is in BCNF if and only if for every non-trivial functional dependency X -> Y, X is a superkey of the relation.

Comparison Summary:
- 1NF eliminates repeating groups.
- 2NF eliminates partial functional dependencies.
- 3NF eliminates transitive functional dependencies.
- BCNF eliminates remaining functional dependency anomalies where determinant is not a candidate key.
"""
page3.insert_text((50, 60), text_p3, fontsize=11)

doc.save("data/samples/dbms.pdf")
doc.close()
print("Generated data/samples/dbms.pdf (3 pages)")

# 2. Generate students.csv
students_data = [
    {"student_id": 101, "name": "Akhil", "semester": 6, "subject": "DBMS", "marks": 85, "grade": "A"},
    {"student_id": 102, "name": "Rahul", "semester": 6, "subject": "DBMS", "marks": 72, "grade": "B"},
    {"student_id": 103, "name": "Anu", "semester": 6, "subject": "DBMS", "marks": 95, "grade": "A+"},
    {"student_id": 104, "name": "Priya", "semester": 6, "subject": "OS", "marks": 88, "grade": "A"},
    {"student_id": 105, "name": "Sneha", "semester": 6, "subject": "DBMS", "marks": 92, "grade": "A+"},
    {"student_id": 106, "name": "Vikram", "semester": 6, "subject": "Networks", "marks": 78, "grade": "B+"},
    {"student_id": 107, "name": "Kavya", "semester": 6, "subject": "DBMS", "marks": 96, "grade": "A+"},
    {"student_id": 108, "name": "Rohan", "semester": 6, "subject": "DBMS", "marks": 64, "grade": "C"},
    {"student_id": 109, "name": "Meera", "semester": 6, "subject": "OS", "marks": 91, "grade": "A+"},
    {"student_id": 110, "name": "Arjun", "semester": 6, "subject": "DBMS", "marks": 89, "grade": "A"}
]
df = pd.DataFrame(students_data)
df.to_csv("data/samples/students.csv", index=False)
print("Generated data/samples/students.csv (10 rows)")
