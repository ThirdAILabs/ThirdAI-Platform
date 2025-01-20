// /app/metadata/sampleData.ts
export interface MetadataAttribute {
  attribute_name: string;
  description: string;
  value: string;
}

export interface DocumentMetadata {
  document_id: string;
  document_name: string;
  metadata_attributes: MetadataAttribute[];
}

export const sampleDocuments: DocumentMetadata[] = [
  {
    document_id: 'doc1',
    document_name: 'AirConditioner_Brand_Analysis.pdf',
    metadata_attributes: [
      {
        attribute_name: 'Brand',
        description: 'Brand of the air conditioner.',
        value: 'Haire',
      },
      {
        attribute_name: 'Model',
        description: 'Model number of the air conditioner.',
        value: 'HA-3000',
      },
    ],
  },
  {
    document_id: 'doc2',
    document_name: 'Energy_Efficiency_Report.pdf',
    metadata_attributes: [
      {
        attribute_name: 'Brand',
        description: 'Brand of the air conditioner.',
        value: 'CoolAir',
      },
      {
        attribute_name: 'Certification',
        description: 'Energy efficiency certification status.',
        value: 'Certified',
      },
    ],
  },
  // Add more sample documents as needed
];
