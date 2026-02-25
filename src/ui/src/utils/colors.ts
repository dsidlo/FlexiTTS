export const getColorForCharacter = (characterName: string, _index: number): string => {
  if (characterName.toLowerCase() === 'narrator') {
    return '#808080'; // Grey for narrator
  }
  
  // A simple predefined palette or hash algorithm
  const palette = [
    '#3498db', '#e74c3c', '#2ecc71', '#f1c40f', '#9b59b6',
    '#e67e22', '#1abc9c', '#34495e', '#d35400', '#c0392b'
  ];
  
  // Hash string to index
  let hash = 0;
  for (let i = 0; i < characterName.length; i++) {
    hash = characterName.charCodeAt(i) + ((hash << 5) - hash);
  }
  return palette[Math.abs(hash) % palette.length];
};
