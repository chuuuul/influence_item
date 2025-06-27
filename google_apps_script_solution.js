/**
 * Google Apps Script를 이용한 Google Sheets 연동 솔루션
 * 이 스크립트를 Google Sheets에서 실행하여 webhook 엔드포인트 생성
 */

// 상수 정의
const SHEET_ID = '1hPkWFJ_FJ6YTwAIOpEbkHhs6bEAFIx2AuWfKNWM'; // 실제 시트 ID로 변경
const SHEET_NAME = 'AnalysisResults'; // 시트 이름

/**
 * N8n에서 호출할 수 있는 웹앱 엔드포인트
 * POST 요청으로 데이터를 받아 Google Sheets에 추가
 */
function doPost(e) {
  try {
    // 요청 데이터 파싱
    const data = JSON.parse(e.postData.contents);
    console.log('받은 데이터:', data);
    
    // 시트 열기
    const spreadsheet = SpreadsheetApp.openById(SHEET_ID);
    let sheet = spreadsheet.getSheetByName(SHEET_NAME);
    
    // 시트가 없으면 생성
    if (!sheet) {
      sheet = spreadsheet.insertSheet(SHEET_NAME);
      
      // 헤더 추가
      const headers = [
        '시간', '채널명', '연예인', '제품명', '브랜드', 
        '카테고리', '신뢰도', '감정', '상태', '테스트노트'
      ];
      sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
      
      // 헤더 스타일링
      const headerRange = sheet.getRange(1, 1, 1, headers.length);
      headerRange.setBackground('#4285f4');
      headerRange.setFontColor('white');
      headerRange.setFontWeight('bold');
    }
    
    // 데이터 추가
    if (data.type === 'single') {
      addSingleRow(sheet, data.payload);
    } else if (data.type === 'batch') {
      addBatchRows(sheet, data.payload);
    } else if (data.type === 'test') {
      addTestData(sheet);
    }
    
    // 성공 응답
    return ContentService
      .createTextOutput(JSON.stringify({
        success: true,
        message: '데이터가 성공적으로 추가되었습니다.',
        timestamp: new Date().toISOString(),
        sheetUrl: spreadsheet.getUrl()
      }))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch (error) {
    console.error('오류 발생:', error);
    
    // 에러 응답
    return ContentService
      .createTextOutput(JSON.stringify({
        success: false,
        error: error.toString(),
        timestamp: new Date().toISOString()
      }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * GET 요청 처리 (상태 확인용)
 */
function doGet(e) {
  try {
    const spreadsheet = SpreadsheetApp.openById(SHEET_ID);
    const sheet = spreadsheet.getSheetByName(SHEET_NAME);
    
    let rowCount = 0;
    if (sheet) {
      rowCount = sheet.getLastRow() - 1; // 헤더 제외
    }
    
    return ContentService
      .createTextOutput(JSON.stringify({
        success: true,
        message: 'Google Sheets 연동이 활성화되어 있습니다.',
        sheetName: SHEET_NAME,
        totalRows: rowCount,
        sheetUrl: spreadsheet.getUrl(),
        timestamp: new Date().toISOString()
      }))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch (error) {
    return ContentService
      .createTextOutput(JSON.stringify({
        success: false,
        error: error.toString()
      }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * 단일 행 추가
 */
function addSingleRow(sheet, data) {
  const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 19);
  
  const row = [
    data.timestamp || timestamp,
    data.channel_name || '',
    data.celebrity_name || '',
    data.product_name || '',
    data.brand || '',
    data.category || '',
    data.confidence || '',
    data.sentiment || '',
    data.status || '',
    data.notes || ''
  ];
  
  sheet.appendRow(row);
  console.log('단일 행 추가 완료:', row);
}

/**
 * 여러 행 일괄 추가
 */
function addBatchRows(sheet, dataArray) {
  const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 19);
  
  const rows = dataArray.map(data => [
    data.timestamp || timestamp,
    data.channel_name || '',
    data.celebrity_name || '',
    data.product_name || '',
    data.brand || '',
    data.category || '',
    data.confidence || '',
    data.sentiment || '',
    data.status || '',
    data.notes || ''
  ]);
  
  if (rows.length > 0) {
    const startRow = sheet.getLastRow() + 1;
    sheet.getRange(startRow, 1, rows.length, rows[0].length).setValues(rows);
    console.log(`${rows.length}개 행 일괄 추가 완료`);
  }
}

/**
 * 테스트 데이터 추가
 */
function addTestData(sheet) {
  const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 19);
  
  const testData = [
    [timestamp, '테스트 채널', '아이유', '맥북 프로', 'Apple', '전자제품', '0.95', 'positive', 'needs_review', 'Google Apps Script 테스트'],
    [timestamp, '뷰티 채널', '이사배', '립스틱', '샤넬', '뷰티', '0.87', 'positive', 'approved', 'API 연동 테스트 완료']
  ];
  
  const startRow = sheet.getLastRow() + 1;
  sheet.getRange(startRow, 1, testData.length, testData[0].length).setValues(testData);
  console.log('테스트 데이터 추가 완료');
}

/**
 * 수동 테스트 함수 (Apps Script 에디터에서 실행)
 */
function manualTest() {
  try {
    const spreadsheet = SpreadsheetApp.openById(SHEET_ID);
    let sheet = spreadsheet.getSheetByName(SHEET_NAME);
    
    if (!sheet) {
      sheet = spreadsheet.insertSheet(SHEET_NAME);
      const headers = [
        '시간', '채널명', '연예인', '제품명', '브랜드', 
        '카테고리', '신뢰도', '감정', '상태', '테스트노트'
      ];
      sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    }
    
    addTestData(sheet);
    
    console.log('수동 테스트 완료!');
    console.log('시트 URL:', spreadsheet.getUrl());
    
  } catch (error) {
    console.error('수동 테스트 실패:', error);
  }
}