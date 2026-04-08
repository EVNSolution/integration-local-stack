# ops-derived fixtures

이 디렉토리는 운영 DB의 분포를 참고해 가명화한 로컬 fixture만 저장한다.

원칙:
- 운영 원본 row dump를 저장하지 않는다.
- fixture는 반복 가능한 local stack smoke 용도다.
- 각 서비스 DB write는 서비스 소유 management command로만 수행한다.

주요 파일:
- ops-derived-sample.json: 가명화된 다건 로컬 fixture bundle
