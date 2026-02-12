curl -X POST http://localhost:5000/impact-tree \
-H "Content-Type: application/json" \
-d '{
    "root_type": "institutions",
    "root_id": 78577930,
    "breakdowns": [
        {"node": "subfields", "sourceSide": true},
        {"node": "countries", "sourceSide": false}
    ]
}'
